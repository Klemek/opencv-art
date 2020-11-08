import time
import rtmidi.midiutil
import rtmidi
import mido

midi_addr_to_parameter_index = {16: 0, 20: 1, 24: 2}

controls = {25: "previous", 26: "next"}


class MidiController:
    def __init__(self, orchestrator):
        self.o = orchestrator
        midiin = rtmidi.MidiIn(
            rtmidi.midiutil.get_api_from_environment(rtmidi.API_UNSPECIFIED)
        )
        ports = midiin.get_ports()
        for i in range(len(ports)):
            if "MIDI Mix" in ports[i]:
                self.port_id = i
                print("Found MIDI Mix at port", self.port_id)

        try:
            self.midiin, self.port_name = rtmidi.midiutil.open_midiinput(self.port_id)
            self.midiout, _ = rtmidi.midiutil.open_midioutput(self.port_id)
        except (EOFError, KeyboardInterrupt):
            print("No midi.")

        self.buttons = [ToggleButton(self.midiout, i) for i in range(25)]
        self.buttons += [TriggerButton(self.midiout, i) for i in [25, 26]]

        for button in self.buttons:
            button.on()
            time.sleep(0.01)
        for button in self.buttons:
            button.off()
            time.sleep(0.01)

        self.buttons_by_id = {}
        for button in self.buttons:
            self.buttons_by_id[button.id] = button

        print("Attaching MIDI input callback handler to", self.port_name)
        print(self.o.current_filter)
        self.midiin.set_callback(MidiInputHandler(self.port_name, self))


class MidiInputHandler:
    def __init__(self, port, controller):

        self.port = port
        self._wallclock = time.time()
        self.buttons_by_id = controller.buttons_by_id
        self.o = controller.o
        self.filter = self.o.current_filter

    def normalize(self, value):
        return value / 127

    def __call__(self, event, data=None):
        message, deltatime = event
        self._wallclock += deltatime
        print("[%s] @%0.6f %r" % (self.port, self._wallclock, message))
        addr = message[1]
        value = self.normalize(message[2])

        if self.buttons_by_id.get(addr):
            if message[0] == 144:  # note ON
                if isinstance(self.buttons_by_id.get(addr), ToggleButton):
                    self.buttons_by_id[addr].toggle()
                if isinstance(self.buttons_by_id.get(addr), TriggerButton):
                    self.buttons_by_id[addr].on()

                action = controls.get(addr)
                if action == "next":
                    self.o.next_filter()
                if action == "previous":
                    self.o.prev_filter()
            if message[0] == 128:  # note OFF
                if isinstance(self.buttons_by_id.get(addr), TriggerButton):
                    self.buttons_by_id[addr].off()

        if midi_addr_to_parameter_index.get(addr, None) is None:
            return
        parameter_index = midi_addr_to_parameter_index[addr]
        self.o.current_filter.set_parameter(parameter_index, value)


class ToggleButton:
    def __init__(self, midiout, id):
        self.id = id
        self.midiout = midiout
        self.state = False

    def toggle(self):
        if self.state:
            self.off()
        else:
            self.on()

    def on(self):
        self.state = True
        m = [0x90, self.id, 127]
        self.midiout.send_message(m)

    def off(self):
        self.state = False
        m = [0x90, self.id, 0]
        self.midiout.send_message(m)


class TriggerButton:
    def __init__(self, midiout, id):
        self.id = id
        self.midiout = midiout

    def on(self):
        m = [0x90, self.id, 127]
        self.midiout.send_message(m)

    def off(self):
        m = [0x90, self.id, 0]
        self.midiout.send_message(m)
