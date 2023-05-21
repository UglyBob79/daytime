import hassapi as hass
import config
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

    slots = [
        'morning',
        'day',
        'evening',
        'night'
    ]

    day_names = {
        0 : 'monday',
        1 : 'tuesday',
        2 : 'wednesday',
        3 : 'thursday',
        4 : 'friday',
        5 : 'saturday',
        6 : 'sunday'
    }

    time_slot_entity = 'input_select.daytime_slot'

    #fake_time = datetime.fromisoformat('2023-05-20 18:15:47')
    
    config = None

    timers = {
        'morning' : None,
        'day' : None,
        'evening' : None,
        'night' : None
    }

    daytime_slot = None
    # TODO Remove current and use only daytime_slot
    current = None

    def initialize(self):
        self.log("Starting day time app")

        self.config = self.load_config()

        self.setup()

    def load_config(self):
        self.log("Loading config...")
        
        try:
            schedule = self.args['schedule']

            config = {}

            # build the internal config from the yaml config, it will get
            # verified partly by accessing the keys
            for day_idx, day_name in DayTime.day_names.items():
                config[day_name] = {}

                for slot in DayTime.slots:
                    self.log(schedule[day_name][slot])
                    config[day_name][slot] = {
                        'type': schedule[day_name][slot]['type'],
                        'time': schedule[day_name][slot]['time']
                        # TODO verify time format
                    }
        except KeyError as e:
            self.log("Config error: Missing key '%s'" % (e))
            # re-throw to halt execution
            raise

        return config

    def setup(self):
        # create an input selector for our time of day slot
        self.daytime_slot = self.create_time_slot_selector()

        now = self.get_time()

        self.calc_current(now)

        self.log("Current: %s" % self.current)

        self.schedule_next_timer(now)

    def create_time_slot_selector(self):
        initial_value = DayTime.slots[0]

        state_attributes = {
            "options": DayTime.slots,
            "initial": initial_value,
        }

        self.set_state(DayTime.time_slot_entity, state=initial_value, attributes=state_attributes)
        
        return DayTime.time_slot_entity

    def calc_current(self, now: datetime):
        time_now = now.time()

        self.log("Time: %s" % (time_now))

        day_schedule = self.gen_day_schedule(now)

        self.log("Day schedule (%s):\n %s" %
            (DayTime.day_names[now.weekday()], pprint.pformat(day_schedule)))

        # Search backwards to find the slot we're currently started
        for slot in DayTime.slots[::-1]:
            if time_now >= day_schedule[slot]:
                self.current = slot
                self.set_state(self.daytime_slot, state=slot)
                break

    def schedule_next_timer(self, now: datetime):
        next_slot = self.next_slot(self.current)

        self.log("Next slot: %s" % (next_slot))

        # If next slot is morning, we should check the next day
        if next_slot == 'morning':
            now += timedelta(days=1)

        day_schedule = self.gen_day_schedule(now)

        self.log("Day schedule next (%s):\n %s" %
            (DayTime.day_names[now.weekday()], pprint.pformat(day_schedule)))

        slot_time = day_schedule[next_slot]

        self.log("Next slot (%s) time: %s" % (next_slot, slot_time))

        self.run_once(self.slot_timer, slot_time, slot=next_slot)

    def slot_timer(self, kwargs):
        self.log("Slot Timer: (%s, %s)" % (self.current, kwargs['slot']))

        self.current = kwargs['slot']
        
        self.set_state(self.daytime_slot, state=kwargs['slot'])

        self.schedule_next_timer(self.get_time())

    def next_slot(self, slot: str):
        return DayTime.slots[(DayTime.slots.index(slot) + 1) % len(DayTime.slots)]

    def get_slot_time(self, date, slot: str):
        weekday = date.weekday()

        # Weekday or weekend?
        day_config = self.config[DayTime.day_names[weekday]]

        slot_config = day_config[slot]

        slot_time = None

        if slot_config['type'] == 'fixed':
            slot_time = self.get_fixed_time(date, slot_config['time'])

            self.log("Fixed slot time: %s" % (slot_time))

        elif slot_config['type'] == 'dynamic':
            slot_time = self.get_real_time(date, slot_config['time'])

            self.log("Real time result: %s" % (slot_time))

        return slot_time

    def get_real_time(self, date, dyn_config):
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
                real_time = self.get_fixed_time(date, dyn_time)

            self.log("Real time (%s): %s" % (dyn_time, real_time))

            if result is None or real_time < result:
                result = real_time

        return result

    def get_fixed_time(self, date, time_str):
        fixed_time = datetime.strptime(time_str, '%H:%M').time()

        return fixed_time

    def gen_day_schedule(self, date: datetime):
        # We should calculate the real time slots for this day
        day_schedule = {
            'morning' : None,
            'day' : None,
            'evening' : None,
            'night' : None
        }

        try:
            for slot in day_schedule.keys():
                slot_time = self.get_slot_time(date, slot)

                day_schedule[slot] = slot_time

            return day_schedule

        except KeyError as e:
            self.log("Error in config, key doesn't exist: %s" % str(e))
            return None

    def get_time(self):
        if hasattr(self, 'fake_time'):
            return self.fake_time
        else:
            return datetime.now()
