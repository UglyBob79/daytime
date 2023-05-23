# DayTime - Day Time Slot Scheduler for AppDaemon 

*DayTime is an [AppDaemon](https://github.com/home-assistant/appdaemon) app which is used to schedule time slots for every day of the week. These slots can then be used for triggering home automations, instead of using specific time values.*

## Installation

Use this [link](https://github.com/benleb/ad-ench-ad3/releases) to download the `daytime` directory to your local `apps` directory in appdaemon, then add the configuration to enable the `daytime` module.

## Prerequisites 

As this is an AppDaemon application, you would of course need AppDaemon to run it. It can be installed as a docker container using these [instructions](https://appdaemon.readthedocs.io/en/latest/INSTALL.html) or as an addon to Home Assistant if you are using the supervised version of Home Assistant.

## Usage

This application could be used for multiple purposes, but the intent was to specify a schedule and then let other apps or Home assistant listen to state changes from the entity representing the current time slot of the day. This entity is currently hard-coded as `input_select.daytime_slot` and will be set up as read-only to prevent other apps or users from changing it. By default, the time slot can be any of the values `morning`, `day`, `evening` or `night`, but these names and number of slots can be overriden in config. All defined slots must be present in each schedule entry.

## App configuration

DayTime needs to be configured with at least a schedule for the week. It can be configured either directly in AppDaemon's `apps.yaml` config file or in a separate `daytime.yaml` in the same folder. Here's an exemplary configuration for this app, showing how the slot names can be overridden and with different schedules for each day of the week.

**Note:** For now, all time values have to be specified in 24H format and they should preferable not overlap as that can create weird behavior.

```yaml
daytime:
  module: daytime
  class: DayTime
  slots:
    - morning
    - day
    - evening
    - night
  schedule:
    monday:
      morning:
        type: fixed
        time: '07:30'
      day:
        type: fixed
        time: '12:00'
      evening:
        type: dynamic
        time: [sunset, '18:00']
      night:
        type: fixed
        time: '23:30'
    tuesday:
      morning:
        type: fixed
        time: '07:30'
      day:
        type: fixed
        time: '12:00'
      evening:
        type: dynamic
        time: [sunset, '18:00']
      night:
        type: fixed
        time: '23:30'
    ...
    sunday:
      morning:
        type: fixed
        time: '10:00'
      day:
        type: fixed
        time: '12:00'
      evening:
        type: dynamic
        time: [sunset, '18:00']
      night:
        type: fixed
        time: '23:59'
```
If your schedule repeats itself, you could instead of adding an entry for each day use the special wildcard days `weekdays`, `weekend` or `any`. See another example below.
```yaml
daytime:
  module: daytime
  class: DayTime
  schedule:
    weekday:
      morning:
        type: fixed
        time: '07:30'
      day:
        type: fixed
        time: '12:00'
      evening:
        type: dynamic
        time: [sunset, '18:00']
      night:
        type: fixed
        time: '23:30'
    saturday:
      morning:
        type: fixed
        time: '07:30'
      day:
        type: fixed
        time: '12:00'
      evening:
        type: dynamic
        time: [sunset, '18:00']
      night:
        type: fixed
        time: '23:30'
    any:
      morning:
        type: fixed
        time: '10:00'
      day:
        type: fixed
        time: '12:00'
      evening:
        type: dynamic
        time: [sunset, '18:00']
      night:
        type: fixed
        time: '23:59'
```
In this schedule, the `weekday` entry would match Monday to Friday, `saturday` would of course match Saturday and `any`would match any day not matched by any other entry, in this case Sundays.

### Configuration

key | optional | type | default | description
-- | -- | -- | -- | --
`module` | False | string | daytime | The module name of the app.
`class` | False | string | DayTime | The name of the python class.
`slots` | True | list | `morning`, `day`, `evening`, `night` | The time slot names of every day.
`schedule` | False | list | N/A | The schedule section used to define the time slots

#### Day configuration

key | optional | description
-- | -- | --
`name` | False | Name of the day we are scheduling. This can also use the wildcards `weekdays`, `weekend` or `any`. If using wildcards, the priority will first be the specific name of the day, then `weekdays`/`weekend` and lastly `any`.
`morning` | False | Morning slot of the day
`day` | False | Day slot of the day
`evening` | False | Evening slot of the day
`night` | False | Night slot of the day

**Note:** These slots and their names can be overriden by adding a `slots` section to the app configuration.

#### Slot configuration

key | optional | type | default | description
-- | -- | -- | -- | --
`type` | False | string | None | The type of slot time. Right now this can be set to `fixed` or `dynamic`.
`time` | False | string or list | None | The time parameter of the slot configuration. If `type` is set to fixed, this should be a time string, i.e. '13:00', which specifies when this time slot begins. If `dynamic`it can be a list of multiple values, which can be either a normal time string or any of the keywords `sunrise` or `sunset`. If multiple values, the one happening first decides when this slot is triggered.
