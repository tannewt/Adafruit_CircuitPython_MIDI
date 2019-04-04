# The MIT License (MIT)
#
# Copyright (c) 2019 Limor Fried for Adafruit Industries, Kevin J. Walters
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`adafruit_midi`
================================================================================

A CircuitPython helper for encoding/decoding MIDI packets over a MIDI or UART connection.


* Author(s): Limor Fried, Kevin J. Walters

Implementation Notes
--------------------

**Hardware:**



**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

import usb_midi
import time

from .midi_message import MIDIMessage

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_MIDI.git"

class RingBuffer:
    def __init__(self, size):
        self._buf = bytearray(size)
        self._start = 0
        self._current_size = 0

    def append(self, value):
        if len(self._buf) == self._current_size:
            raise RuntimeError("Buffer full")
        self._buf[(self._start + self._current_size) % len(self._buf)] = value
        self._current_size += 1

    def popleft(self):
        if self._current_size == 0:
            raise IndexError("Empty")
        v = self._buf[self._start]
        self._start = (self._start + 1) % len(self._buf)
        self._current_size -= 1
        return v

    def __len__(self):
        return self._current_size

    def __getitem__(self, index):
        if isinstance(index, slice):
            step = index.step if index.step else 1
            length = (index.stop - index.start) // step
            b = bytearray(length)
            for i in range(length):
                b[i] = self[step*i]
            return b
        return self._buf[(self._start + index) % len(self._buf)]

class MIDI:
    """MIDI helper class."""

    NOTE_ON = 0x90
    NOTE_OFF = 0x80
    PITCH_BEND = 0xE0
    CONTROL_CHANGE = 0xB0

    def __init__(self, midi_in=usb_midi.ports[0], midi_out=usb_midi.ports[1], *,
                 in_channel=None, out_channel=0, debug=False, in_buf_size=30):
        self._midi_in = midi_in
        self._midi_out = midi_out
        self.in_channel = in_channel
        self.out_channel = out_channel
        self._debug = debug
        # This input buffer holds what has been read from midi_in
        self._in_buf = RingBuffer(in_buf_size)
        self._in_buf_start = 0
        self._in_buf2 = bytearray(4)
        self._outbuf = bytearray(4)
        self._skipped_bytes = 0

    @property
    def in_channel(self):
        """The incoming MIDI channel. Must be 0-15. Correlates to MIDI channels 1-16, e.g.
        ``in_channel(3)`` will listen on MIDI channel 4.
        Can also listen on multiple channels, e.g. ``in_channel((0,1,2))``
        will listen on MIDI channels 1-3 or ``in_channel("ALL")`` for every channel.
        Default is None."""
        return self._in_channel

    @in_channel.setter
    def in_channel(self, channel):
        if channel is None or (isinstance(channel, int) and 0 <= channel <= 15):
            self._in_channel = channel
        elif isinstance(channel, str) and channel == "ALL":
            self._in_channel = MIDIMessage.ALL_CHANNELS
        elif isinstance(channel, tuple) and all(0 <= c <= 15 for c in channel):
            self._in_channel = channel
        else:
            raise RuntimeError("Invalid input channel")

    @property
    def out_channel(self):
        """The outgoing MIDI channel. Must be 0-15. Correlates to MIDI channels 1-16, e.g.
        ``out_channel(3)`` will send to MIDI channel 4. Default is 0."""
        return self._out_channel

    @out_channel.setter
    def out_channel(self, channel):
        if not 0 <= channel <= 15:
            raise RuntimeError("Invalid output channel")
        self._out_channel = channel

    def receive(self):
        """Read messages from MIDI port, store them in internal read buffer, then parse that data
        and return the first MIDI message (event).

        Returns (MIDIMessage object, channel) or (None, None) for nothing.
        """
        num_read = self._midi_in.readinto(self._in_buf2)
        if num_read and num_read > 0:
            if self._debug:
                print("Receiving: ", [hex(self._in_buf2[i]) for i in range(num_read)])
            for i in range(num_read):
                self._in_buf.append(self._in_buf2[i])

        (msg, start, endplusone, skipped, channel) = MIDIMessage.from_message_bytes(self._in_buf, self._in_channel)
        for _ in range(endplusone):
            self._in_buf.popleft()

        self._skipped_bytes += skipped

        # msg could still be None at this point, e.g. in middle of monster SysEx
        return (msg, channel)

    def send(self, msg, channel=None):
        """Sends a MIDI message.

        :param msg: Either a MIDIMessage object or a sequence (list) of MIDIMessage objects.
        :param int channel: Channel number, if not set the ``out_channel`` will be used.

        """
        if channel is None:
            channel = self.out_channel
        if isinstance(msg, MIDIMessage):
            data = msg.as_bytes(channel=channel)
        else:
            data = bytearray()
            for each_msg in msg:
                data.extend(each_msg.as_bytes(channel=channel))

        self._send(data, len(data))

    def note_on(self, note, vel, channel=None):
        """Sends a MIDI Note On message.

        :param int note: The note number. Must be 0-127.
        :param int vel: The note velocity. Must be 0-127.

        """
        self._generic_3(self.NOTE_ON, note, vel, channel)

    def note_off(self, note, vel, channel=None):
        """Sends a MIDI Note Off message.

        :param int note: The note number. Must be 0-127.
        :param int vel: The note velocity. Must be 0-127.

        """
        self._generic_3(self.NOTE_OFF, note, vel, channel)

    def pitch_bend(self, value, channel=None):
        """Send a MIDI Pitch Wheel message.

        :param int value: Range is 0-16383. A ``value`` of 8192 equates to no pitch bend, a value
                          of less than 8192 equates to a negative pitch bend, and a value of more
                          than 8192 equates to a positive pitch bend.

        """
        self._generic_3(self.PITCH_BEND, value & 0x7F, value >> 7, channel)

    def control_change(self, control, value, channel=None):
        """Sends a MIDI CC message.

        :param int control: The controller number. Must be 0-127.
        :param int value: The control value. Must be 0-127.

        """
        self._generic_3(self.CONTROL_CHANGE, control, value, channel)

    def _generic_3(self, cmd, arg1, arg2, channel=None):
        if not 0 <= arg1 <= 0x7F:
            raise RuntimeError("Argument 1 value %d invalid" % arg1)
        if not 0 <= arg2 <= 0x7F:
            raise RuntimeError("Argument 2 value %d invalid" % arg2)
        if channel is None:
            channel = self._out_channel
        self._outbuf[0] = (cmd & 0xF0) | (channel & 0x0f)
        self._outbuf[1] = arg1
        self._outbuf[2] = arg2
        self._send(self._outbuf, 3)

    def _send(self, packet, num):
        if self._debug:
            print("Sending: ", [hex(i) for i in packet[:num]])
        self._midi_out.write(packet, num)
