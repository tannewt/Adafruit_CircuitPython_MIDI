# The MIT License (MIT)
#
# Copyright (c) 2019 Kevin J. Walters
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


* Author(s): Kevin J. Walters

Implementation Notes
--------------------

**Hardware:**



**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

from .midi_message import MIDIMessage, note_parser

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_MIDI.git"


class NoteOff(MIDIMessage):
    _STATUS = 0x80
    _STATUSMASK = 0xf0
    _LENGTH = 3
    _CHANNELMASK = 0x0f

    def __init__(self, note, velocity):
        self.note = note_parser(note)
        self.velocity = velocity
        if not 0 <= self.note <= 127 or not 0 <= self.velocity <= 127:
            raise ValueError("Out of range")

    # channel value is mandatory
    def as_bytes(self, channel=None):
        return bytearray([self._STATUS | (channel & self._CHANNELMASK),
                         self.note, self.velocity])

    @classmethod
    def from_bytes(cls, databytes):
        return cls(databytes[1], databytes[2])

NoteOff.register_message_type()
