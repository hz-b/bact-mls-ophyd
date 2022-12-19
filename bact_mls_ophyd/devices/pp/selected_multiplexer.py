import sys
import threading
import time

import numpy as np
from bact2.ophyd.devices.raw.multiplexer_state_machine import MuxerState
from bact2.ophyd.devices.raw.quad_list import quadrupoles
from bact2.ophyd.devices.utils import signal_with_validation, ReachedSetPoint
from bluesky.protocols import Movable
from ophyd import (Component as Cpt, Device, EpicsSignal, EpicsSignalRO, Kind, PVPositionerPC, Signal, )

from ophyd.device import DynamicDeviceComponent as DDC, Component
from ophyd.status import AndStatus, SubscriptionStatus, Status

t_super = PVPositionerPC
t_super = ReachedSetPoint.ReachedSetpointEPS

_muxer_off = "Mux OFF"
_request_off = "Off"

_t_super = PVPositionerPC


class MultiplexerSelector(_t_super):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # use a long validation time let's see if there are more changes
        validation_time = self.validation_time.get()
        self.mux_switch_validate = signal_with_validation.FlickerSignal(self.readback, timeout=3,
            validation_time=validation_time)
        self._timestamp = time.time()
        self.state_machine = MuxerState()
        self.lock = threading.Lock()

    #: read back the name of the magnet the muxer is connected to
    readback = Cpt(EpicsSignal, ":name")

    #: store the one that was explicitily set
    selected = Cpt(Signal, name="selected", value="non stored")

    #: setpoint as index number
    setpoint_num = Cpt(Signal, name="setpoint_num", value=-1)

    #: selected as index number
    selected_num = Cpt(Signal, name="selected_num", value=-1)

    #: switch power converter off ?
    off = Cpt(EpicsSignal, ":off", name="off")

    #: are the relays enabled?
    relay = Cpt(EpicsSignalRO, ":disable")

    #: Todo: check if it is still working!
    relay_ps = Cpt(EpicsSignalRO, ":relay_ps")

    #: How long did it take to set the value
    set_time = Cpt(Signal, name="set_time", value=-1)

    #: How long did it take to set the value
    last_wait = Cpt(Signal, name="last_wait", value=-1)

    validation_time = Cpt(Signal, name="validation_time", value=2, kind=Kind.config)

    state = Cpt(Signal, name="state", value="undefined")

    settle_time = Cpt(Signal, name="settle_time", value=0.5, kind=Kind.config)
    timeout = Cpt(Signal, name="timeout", value=10.0, kind=Kind.config)

    def checkPowerconverterMembers(self):
        # The multiplexer power converter
        pc = self.parent.power_converter
        pc.setpoint
        pc.setpoint.get
        pc.readback.get

    def initStateMachine(self):
        # Get the allowed names
        pcs = self.parent.wrapper.pcs
        magnet_names = [name for name in dir(pcs)]

        currently_set = self.readback.get()
        if currently_set == _muxer_off:
            self.state_machine.set_off()
        elif currently_set in magnet_names:
            self.state_machine.set_selected()
            self.selected.put(currently_set)
        else:
            self.state_machine.failed()
            txt = f"currently set name {currently_set} is unknown"
            self.log.error(txt)
            raise AssertionError(txt)

        state = self.state_machine.state
        self.log.debug("Initialised  muxer representation to"
                       "selected = {currently_set} state machine {state}")

    def checkMuxSwitches(self, *, selected, old_value, value, **kwargs):
        """Callback to follow that mux switches happen as expected

        The muxer behaves in the following manner:

        * If it was off:
            1. response: the name of the selceted device
            2. response: Mux Off
            3. response: the name of the selected device

        * If a power converter was selected
            1. response: Mux Off
            2. response: the name of the selected device

        * And then there is one more thing:
           1. It has directly set from the last selected device
              to the requested one

          Typically not used as the device checks that now action is required

        Thou shall use state machines!
        How true it is
        """
        state = self.state_machine.state
        t_values_txt = (f'switching: value="{value}" old_value="{old_value}" state={state}')
        if old_value == value:
            self.log.warning("Checking " + t_values_txt)

        if self.state_machine.is_failed:
            raise MuxerSwitchError("State machine in failed state:" + t_values_txt)

        txt_expected_target = (f"With {t_values_txt}: expected {selected} as new (and final) value")

        if self.state_machine.is_off:
            if value == selected:
                self.log.info("Setting state machine to is_selected: selected {selected} value {value}")
                self.state_machine.set_selected()
                return True
            else:
                txt = "Switching from off " + txt_expected_target
                self.log.error(txt)
                raise MuxerSwitchError(txt)

        if self.state_machine.is_intermediate:
            if value == selected:
                self.log.info("Setting state machine to is_selected: selected {selected} value {value}")
                self.state_machine.set_selected()
                return True
            else:
                txt = "Switching from intermediate " + txt_expected_target
                self.log.error(txt)
                raise MuxerSwitchError(txt)

        if self.state_machine.is_off_for_switch:
            if value == _muxer_off:
                self.log.info(f"Setting state machine to off_for_switch: selected {selected} value {value}")
                self.state_machine.set_intermediate()
                # One more turn to go to
                return False
            else:
                txt = (f'Switching from selected: expected to see "{_muxer_off}" but ' + t_values_txt)
                self.log.error(txt)
                raise MuxerSwitchError(txt)

    def switchMuxAndTrace(self, selected_device_name):
        """switch the muxer directly from device

        Checks the changes by following the switching on and off


        Works in the following manner:
           1. a callback trace_cb is registed to readback
           2. the callback trace_cb calls :meth:`checkMuxSwitches`.
              This method checks that the muxer is switched off
              and back to the are made as expected. This method is
              expected to call :meth:`_finished` on set_traced.
           3. When this happens the validate_cb is called. This
              callback uses
              :class:`signal_with_validation.FlickerSignal`.
              This signal is used, as the muxer sends some extra
              value sometimes. FlickerSignal will set the
              device_status to finished when no further data arrives.
           4. Furthermore the readback callback is removed
           5. Finally a callback :func:`store_selected` will be called.
              This stores the name of the selected quadrupole and its
              number.

        """
        state = self.state_machine.state
        self.log.info(f"Multiplexer.switchMuxAndTrace selected {selected_device_name}  state {state}")
        pcs = self.parent.wrapper.pcs
        pc_ac = getattr(pcs, selected_device_name)
        self.log.info("power converter wrapper to use for switch {}".format(pc_ac))

        # is the value already set to the muxer thant the mimic starts
        mux_set_pv_val = False
        # For debug purposes set to true ... have to see if the
        # possible race condition is a real world problem
        mux_set_pv_val = True

        def cb(*, value, old_value, **kwargs):

            nonlocal status_mux
            if not mux_set_pv_val:
                # not yet ready to process
                return False

            self.log.debug(f"muxer switch cb: value {value} old_value {old_value}"
                           f" selected {selected_device_name} state {self.state_machine.state}")
            with self.lock:
                try:

                    flag = self.checkMuxSwitches(selected=selected_device_name, value=value, old_value=old_value,
                        **kwargs, )
                except Exception as exc:
                    status.set_exception(exc)
                    self.state_machine.failed()
                    raise exc
            return flag

        def store_selected(status):
            nonlocal selected_device_name

            val = self.readback.get()

            if val != selected_device_name:
                fmt = "Expected that device is selected {} but found device {}"
                raise AssertionError(fmt.format(selected_device_name, val))

            num = quadrupoles.index(val)
            self.log.info("Storing last set to {} as num {}".format(val, num))
            self.selected.put(val)
            self.selected_num.put(num)

            now = time.time()
            dt = now - self._timestamp
            self.set_time.set(dt)
            self.log.debug(f" selected {selected_device_name} state {self.state_machine.state}: required dt {dt}")

        status_mux = SubscriptionStatus(self.readback, cb, run=False, timeout=self.timeout.get(),
            settle_time=self.settle_time.get(), )
        status_mux.add_callback(store_selected)

        if self.state_machine.is_selected:
            # If a magnet is selected the muxer will fire a "Mux_Off"
            # on the next step: thus the state machine has to be set to
            # intermediate to be prepared to handle that correctly
            self.state_machine.set_off_for_switch()
        status_set = pc_ac.set(1)

        def cb_set(status):
            nonlocal mux_set_pv_val
            self.log.info("Switching muxer: variable triggering switch set")
            mux_set_pv_val = True

        status_set.add_callback(cb_set)
        status = AndStatus(status_mux, status_set)
        return status

    def switchMuxOff(self):
        """Switch the muxer if required
        See :meth:`switchMuxAndTrace` for the heavy lifting
        """
        self.log.info(f"Multiplexer.switchMuxOff")

        # What has to be written to the device....
        rbk = self.readback.get()
        self.log.info(f'power converter command to off: rbk "{rbk}"')
        if rbk == "Mux OFF":
            # Already off nothing to do
            txt = f'power converter already off: nothing to do "{rbk}"'
            self.log.info(txt)
            self.state_machine.set_off()
            stat = Status()
            stat.set_finished()
            return stat

        self.state_machine.set_off()
        return AndStatus(self.off.set(1), self.selected.set(_muxer_off))

    def switchPowerconverter(self, name):
        """select the power converter to pack on

        Now directly switching to the power converter required
        """
        self.log.info(f"Multiplexer.switchPowerconverter: Switching multiplexer to {name}")

        # self.checkPpowerconverterMembers()
        pc = self.parent.power_converter

        # Make sure the power converter is off
        check_value = pc.setpoint.get()

        if check_value != 0:
            raise AssertionError(f"Power converter setpoint not 0 but {check_value}: setpoint {pc.setpoint}")

        assert self.readback is not None

        # Short check that power converter is off
        pc = self.parent.power_converter
        flag = pc.isOff()
        if not flag:
            self.log.error("Requesting switch while power converter is running!")
            txt = "Requesting switch for power converter under current"
            txt += pc.isOffText()
            self.log.error(txt)
            raise MuxerSwitchError(txt)

        if name == _request_off:
            return self.switchMuxOff()

        return self.switchMuxAndTrace(name)

    def set(self, value):
        """Select the power converter selector

        Todo:
           Check that the value ios correct at the end
        """
        self.log.info(f"Multiplexer.set: Switching multiplexer to {value}")
        self._timestamp = time.time()
        if value == _request_off:
            num = -1
        else:
            try:
                num = quadrupoles.index(value)
            except Exception as exc:
                self.log.error(f"Trying to lookup {value} in sequence {quadrupoles}")
                raise exc

        self.setpoint_num.put(num)
        self.selected.put(value)
        del num

        self.checkPowerconverterMembers()
        self.mux_switch_validate.tic()
        # Check if the power converter is already selected ...
        selected = self.readback.get()
        if selected == value:
            self.log.info("Not switching muxer already at {}".format(value))
            status = Status()
            status.set_finished()
            return status

        self.log.info("Switching muxer from {} to {}".format(selected, value))

        def cb_for_state_engine(success=False):
            if not success:
                self.state_machine.failed()

        status = self.switchPowerconverter(value)
        status.add_callback(cb_for_state_engine)
        return status

    def trigger(self):
        stat_rbk = self.readback.trigger()
        stat_relay = self.relay.trigger()
        stat_off = self.off.trigger()

        return AndStatus(AndStatus(stat_rbk, stat_relay), stat_off)

    def _switchOff(self):
        # Disabled because this off should only be launched when
        # the power converter is safely set to zero
        # self.log.warning('Switching multiplexer off: disabled for development')

        pc = self.parent.power_converter
        if not pc.isOff():
            txt = pc.isOffText()
            self.log.warning("Muxer selector: muxer power converter still on:"
                             " thus not switching muxer off: pc not considered off as " + txt)
            return

        self.log.warning('Switching multiplexer off: power converter considered off')
        self.off.put(1, use_complete=False)

    def switchOff(self):
        cls_name = self.__class__.__name__
        name = self.name
        try:
            self._switchOff()
        except Exception as exc:
            self.log.error(f"Failed to switch of {cls_name}(name={name}): reason({exc})")

    def stage(self):
        """

        Just for symmetry
        """
        self.initStateMachine()
        return super().stage()

    def unstage(self):
        """

        Todo:
           To be sure that its left over as off
        """
        self.switchOff()
        return super().unstage()

    def stop(self, success=False):
        self.switchOff()


class MuxerSwitchError(ValueError):
    """Switching not as expected"""
