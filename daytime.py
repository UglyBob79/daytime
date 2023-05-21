import hassapi as hass
from datetime import datetime, timedelta, time
import pprint

#
# Daytime App
#
# Args:
#

# TODO what about sunset/sunrise that never happens (up north) or overlaps the next slot?
# TODO sunset/sunrise with offset
# TODO handle weekdays/weekend instead of the specific days

class DayTime(hass.Hass):

    # Default slot names
    slots = [
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

    time_slot_entity = 'input_select.daytime_slot'

    daytime_slot = None
    # TODO Remove current and use only daytime_slot
    current = None

    def initialize(self):
        """
       Initialize this app. This will be called by AppDaemon.
        """

        self.log("Starting day time app")

        self.config = self.load_config()

        self.setup()

    def load_config(self):
        """
        Load the configuration of this app. The configuration is fetched from the apps.yaml in the AppDaemon configuration folder
        """

        self.log("Loading config...")
        
        try:
            # verify optional slots config
            if 'slots' in self.args:
                slots = self.args['slots']

                if not type(slots) == list:
                    self.log("Config Error: slots must be a list")
                    raise ValueError("Invalid configuration format: slots must be a list")

                for slot in slots:
                    if not type(slot) == str:
                        self.log("Config Error: slot name must be a string, not '%s'" % str(slot))
                        raise ValueError("Invalid configuration format: slot names must be a string")

                self.slots = slots

            schedule = self.args['schedule']

            config = {}

            # verify and build the internal config from the yaml config in apps.yaml
            for day_name in DayTime.day_names:
                config[day_name] = {}

                for slot in self.slots:
                    #verify slot time config
                    if schedule[day_name][slot]['type'] == 'fixed':
                        # verify time format
                        # will throw exception on faulty format
                        self.get_fixed_time(schedule[day_name][slot]['time'])
                    elif schedule[day_name][slot]['type'] == 'dynamic':
                        if type(schedule[day_name][slot]['time']) == list:
                            # verify time format
                            # will throw exception or return None on faulty format
                            if self.get_real_time(schedule[day_name][slot]['time']) is None:
                                self.log("Config Error: could not parse time parameter '%s'" % str(schedule[day_name][slot]['time']))
                                raise ValueError("Invalid configuration format: could not parse time parameter'")
                        else:
                            self.log("Config Error: if time type is 'dynamic', time parameter must be a list, not '%s'" % str(schedule[day_name][slot]['time']))
                            raise ValueError("Invalid configuration format: time parameter must be a list, if time type is 'dynamic'")
                    else:
                        self.log("Config Error: time type most be either 'fixed' or 'dynamic', not '%s'" % str(schedule[day_name][slot]['type']))
                        raise ValueError("Invalid configuration format: time type must be 'fixed' or 'dynamic'")

                    config[day_name][slot] = {
                        'type': schedule[day_name][slot]['type'],
                        'time': schedule[day_name][slot]['time']
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

        # create an input selector for our time of day slot
        self.daytime_slot = self.create_time_slot_selector()

        now = self.get_time()

        self.current = self.calc_current_slot(now)
        self.set_state(self.daytime_slot, state=self.current)
        
        self.log("Current slot: %s" % self.current)

        self.schedule_next_timer(now)

    def create_time_slot_selector(self):
        """
        Create a input selector representing the current time slot.

        Returns:
        str: The name of the input selector entity.    
        """

        state_attributes = {
            "options": self.slots,
            "initial": self.slots[0],
        }

        self.set_state(DayTime.time_slot_entity, state=self.slots[0], attributes=state_attributes)
        
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

        day_schedule = self.gen_day_schedule(now)

        self.log("Day schedule (%s):\n %s" %
            (DayTime.day_names[now.weekday()], pprint.pformat(day_schedule)))

        # Search backwards to find the slot we're currently started
        for slot in self.slots[::-1]:
            if time_now >= day_schedule[slot]:
                return slot
                break

        return None

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

        day_config = self.config[DayTime.day_names[weekday]]

        slot_config = day_config[slot]

        slot_time = None

        if slot_config['type'] == 'fixed':
            slot_time = self.get_fixed_time(slot_config['time'])

            self.log("Fixed slot time: %s" % (slot_time))

        elif slot_config['type'] == 'dynamic':
            slot_time = self.get_real_time(slot_config['time'])

            self.log("Dynamic slot time: %s" % (slot_time))

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
            # The sunrise calculation will always be for the current day,
            # but usually it is just used for +1 day or so...
            if dyn_time == 'sunrise':
                real_time = self.sunrise().time()
            elif dyn_time == 'sunset':
                real_time = self.sunset().time()
            else:
                # Probably just a fixed time then, try to convert...
                real_time = self.get_fixed_time(dyn_time)

            self.log("Real time (%s): %s" % (dyn_time, real_time))

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
