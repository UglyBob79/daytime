import hassapi as hass
from datetime import datetime, timedelta, time
import re
import pprint

"""
DayTime - Day Time Slot Scheduler App

This module provides the DayTime app, which allows scheduling time slots for different parts of the day. It is designed to be used with AppDaemon for home automation purposes.

The DayTime app allows you to define a schedule for each day of the week, specifying different time slots such as morning, day, evening, and night. You can configure fixed times or dynamic times based on sunrise or sunset.

To use the DayTime app, define the schedule in the AppDaemon configuration file (apps.yaml) using the 'daytime' section. See the README.md for more information on the configuration options.

Author: Mattias Månsson
"""

# TODO what about sunset/sunrise that never happens (up north) or overlaps the next slot? Think we need to compare datetime instead of time
# TODO handle weekdays/weekend instead of the specific days
# TODO remove type: fixed/dynamic, its not really needed

class DayTime(hass.Hass):

    SUNRISE_PATTERN =   r'^sunrise(?P<offset>[+-][0-9]+)?$'
    SUNSET_PATTERN =    r'^sunset(?P<offset>[+-][0-9]+)?$'

    # Default slot names
    default_slots = [
        'morning',
        'day',
        'evening',
        'night'
    ]

    # Default day names
    day_names = [
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
        'sunday'
    ]

    # helper lists for wild card days
    weekdays = day_names[:5]
    weekend = day_names[5:]

    time_slot_entity = 'input_select.daytime_slot'

    daytime_slot = None
    # TODO Remove current and use only daytime_slot
    current = None

    def initialize(self):
        """
       Initialize this app. This will be called by AppDaemon.
        """

        self.log("Starting day time app")

        config = self.load_config()

        self.slots = config['slots']
        self.schedule = config['schedule']

        self.setup()

    def load_config(self):
        """
        Load the configuration of this app. The configuration is fetched from the apps.yaml in the AppDaemon configuration folder
        """

        self.log("Loading config...")

        config = {}

        try:
            # verify optional slots config
            if 'slots' in self.args:
                slots_cfg = self.args['slots']

                if not type(slots_cfg) == list:
                    self.log("Config Error: slots must be a list.")
                    raise ValueError("Invalid configuration format: slots must be a list.")

                for slot in slots_cfg:
                    if not type(slot) == str:
                        self.log("Config Error: slot name must be a string, not '%s'." % str(slot))
                        raise ValueError("Invalid configuration format: slot names must be a string.")

                config['slots'] = slots_cfg
            else:
                config['slots'] = default_slots

            config['schedule'] = {}
            schedule_cfg = self.args['schedule']

            # verify and build the schedule config
            for day_name in DayTime.day_names:
                # check if the schedule for the day exists
                if day_name in schedule_cfg:
                    day_schedule = schedule_cfg[day_name]
                elif day_name in DayTime.weekdays and 'weekdays' in schedule_cfg:
                    self.log("Using 'weekdays' schedule for '%s'" % day_name)
                    day_schedule = schedule_cfg['weekdays']
                elif day_name in DayTime.weekend and 'weekend' in schedule_cfg:
                    self.log("Using 'weekend' schedule for '%s'" % day_name)
                    day_schedule = schedule_cfg['weekend']
                elif 'any' in schedule_cfg:
                    self.log("Using 'any' schedule for '%s'" % day_name)
                    day_schedule = schedule_cfg['any']
                else:
                    self.log("Config Error: no schedule matching '%s'." % str(day_name))
                    raise ValueError("Invalid configuration format: missing day entries in schedule.")

                config['schedule'][day_name] = {}

                for slot in config['slots']:
                    # verify slot time config
                    if day_schedule[slot]['type'] == 'fixed':
                        # verify time format
                        # will throw exception on faulty format
                        self.get_fixed_time(day_schedule[slot]['time'])
                    elif day_schedule[slot]['type'] == 'dynamic':
                        if type(day_schedule[slot]['time']) == list:
                            # verify time format
                            # will throw exception or return None on faulty format
                            if self.get_real_time(day_schedule[slot]['time']) is None:
                                self.log("Config Error: could not parse time parameter '%s'" % str(day_schedule[slot]['time']))
                                raise ValueError("Invalid configuration format: could not parse time parameter.")
                        else:
                            self.log("Config Error: if time type is 'dynamic', time parameter must be a list, not '%s'." % str(day_schedule[slot]['time']))
                            raise ValueError("Invalid configuration format: time parameter must be a list, if time type is 'dynamic'.")
                    else:
                        self.log("Config Error: time type most be either 'fixed' or 'dynamic', not '%s'." % str(day_schedule[slot]['type']))
                        raise ValueError("Invalid configuration format: time type must be 'fixed' or 'dynamic'.")

                    config['schedule'][day_name][slot] = {
                        'type': day_schedule[slot]['type'],
                        'time': day_schedule[slot]['time']
                    }

        except KeyError as e:
            self.log("Config Error: Missing key '%s'" % (e))
            # re-throw to halt execution
            raise

        return config

    def setup(self):
        """
        Setup the app. Will create an input selector entity that can be used for automations. It will also calculate the initial schedule
        and set up needed timers.
        """

        now = self.get_time()

        self.current = self.calc_current_slot(now)
        self.log("Current slot: %s" % self.current)

        # create an input selector for our time of day slot
        self.daytime_slot = self.create_time_slot_selector(self.current)

        self.schedule_next_timer(now)

    def create_time_slot_selector(self, initial=None):
        """
        Create a input selector representing the current time slot.

        Returns:
        str: The name of the input selector entity.
        """

        initial_slot = initial if initial else self.slots[0]

        state_attributes = {
            "options": self.slots,
            "initial": initial_slot,
        }

        self.set_state(DayTime.time_slot_entity, state=initial_slot, attributes=state_attributes)

        return DayTime.time_slot_entity

    def calc_current_slot(self, now: datetime):
        """
        Calculate what the current (initial) time slot is for a certain time.

        Parameters:
        now (datetime): The time to use for the calculations.

        Returns:
        str: The calculated time slot or None on failure.
        """

        time_now = now.time()

        self.log("Time now: %s" % (time_now))
        self.log("Sunrise today: %s" % (self.sunrise().time()))
        self.log("Sunset today: %s" % (self.sunset().time()))

        day_schedule = self.gen_day_schedule(now)

        self.log("Day schedule (%s):\n %s" %
            (DayTime.day_names[now.weekday()], pprint.pformat(day_schedule)))

        # Search backwards to find the slot we're currently started
        for slot in self.slots[::-1]:
            if time_now >= day_schedule[slot]:
                return slot
                break

        # If we didnt't find a match, it means its the last slot, but it passed midnight, so default to the last slot
        return self.slots[-1]

    def schedule_next_timer(self, now: datetime):
        """
        Schedule a timer to trigger when next time slot occurs.

        Parameters:
        now (datetime): The current time.
        """

        next_slot = self.get_next_slot(self.current)

        self.log("Next slot: %s" % (next_slot))

        # If next slot is the first one, we should check the next day
        if next_slot == self.slots[0]:
            now += timedelta(days=1)

        day_schedule = self.gen_day_schedule(now)

        self.log("Day schedule next (%s):\n %s" %
            (DayTime.day_names[now.weekday()], pprint.pformat(day_schedule)))

        slot_time = day_schedule[next_slot]

        self.log("Next slot (%s) time: %s" % (next_slot, slot_time))

        self.run_once(self.on_slot_timer, slot_time, slot=next_slot)

    def on_slot_timer(self, kwargs):
        """
        Timer event handler for the next slot timer.
        """

        self.log("Slot Timer: (%s, %s)" % (self.current, kwargs['slot']))

        self.current = kwargs['slot']

        self.set_state(self.daytime_slot, state=kwargs['slot'])

        self.schedule_next_timer(self.get_time())

    def get_next_slot(self, slot: str):
        """
        Get the name of the next time slot from a certain time slot.

        Parameters:
        slot (str): The current time slot.

        Returns:
        str: The name of the next time slot.
        """

        return self.slots[(self.slots.index(slot) + 1) % len(self.slots)]

    def get_slot_time(self, date, slot: str):
        """
        Get the time a time slot will occur for a certain day.

        Parameters:
        date (datetime): The date of the day to check.
        slot (str): The name of the slot to check.

        Returns:
        str: A time string representing the beginning time of the slot.
        """

        weekday = date.weekday()

        day_config = self.schedule[DayTime.day_names[weekday]]

        slot_config = day_config[slot]

        slot_time = None

        if slot_config['type'] == 'fixed':
            slot_time = self.get_fixed_time(slot_config['time'])
        elif slot_config['type'] == 'dynamic':
            slot_time = self.get_real_time(slot_config['time'])

        return slot_time

    def get_real_time(self, dyn_config):
        """
        Get the real time value for a dynamic config for a certain day.

        Parameters:
        dyn_config ([str]): A list of dynamic time strings.

        str: A time string representing the the real time of the dynamic slot time.
        """

        result = None

        for dyn_time in dyn_config:
            # The sunrise calculation will always be for the current day, but
            # its usually max one day wrong, which for these calculations
            # doesn't really matter much

            # TODO remove duplicated code, maybe one common pattern?
            match = re.match(self.SUNRISE_PATTERN, dyn_time)
            if match:
                # check if using optional offset
                offset = 0
                if match.group('offset') is not None:
                    offset = int(match.group('offset'))
                real_time = (self.sunrise() + timedelta(minutes=offset)).time()

                if result is None or real_time < result:
                    result = real_time

                continue

            match = re.match(self.SUNSET_PATTERN, dyn_time)
            if match:
                # check if using optional offset
                offset = 0
                if match.group('offset') is not None:
                    offset = int(match.group('offset'))
                real_time = (self.sunset() + timedelta(minutes=offset)).time()

                if result is None or real_time < result:
                    result = real_time

                continue

            # Probably just a fixed time then, try to convert...
            real_time = self.get_fixed_time(dyn_time)

            if result is None or real_time < result:
                result = real_time

        return result

    def get_fixed_time(self, time_str):
        """
        Get the fixed time from a time string with the format HH:MM.

        Parameters:
        time_str (str): The time string representation.

        Return:
        datetime: A datetime time object.
        """

        fixed_time = datetime.strptime(time_str, '%H:%M').time()

        return fixed_time

    def gen_day_schedule(self, date: datetime):
        """
        Generate the schedule for a certain day.

        Parameters:
        date (datetime): The date of the day to check.

        Returns:
        dict: The schedule for the day or None on failure.
        """

        # We should calculate the real time slots for this day
        day_schedule = {slot: None for slot in self.slots}

        try:
            for slot in day_schedule.keys():
                slot_time = self.get_slot_time(date, slot)

                day_schedule[slot] = slot_time

            return day_schedule

        except KeyError as e:
            self.log("Error in config, key doesn't exist: %s" % str(e))
            return None

    def get_time(self):
        """
        Get the current time. Wrapping wrapping datetime.now() in case we want to fake the current time for testing.

        Returns:
        datetime: The current time.
        """

        if hasattr(self, 'fake_time'):
            return self.fake_time
        else:
            return datetime.now()
