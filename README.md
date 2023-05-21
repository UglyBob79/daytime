# DayTime - Day Time Slot Scheduler | AppDaemon 4.x Edition

*DayTime is an [AppDaemon](https://github.com/home-assistant/appdaemon) app which is used to schedule time slots for every day of the week, that can be used for scheduling home automation by time of day.*

## Installation

Use this [link](https://github.com/benleb/ad-ench-ad3/releases) to download the `daytime` directory to your local `apps` directory in appdaemon, then add the configuration to enable the `daytime` module.

## Prerequisites 

As this is an AppDaemon application, you would of course need AppDaemon to run it. It can be installed as a docker container using these [instructions](https://appdaemon.readthedocs.io/en/latest/INSTALL.html) or as an addon to Home Assistant if you are using the supervised version of Home Assistant.

## App configuration

DayTime needs a schedule to run and it is configured directly in the AppDaemon's apps.yaml file as a schedule sub-section for this app. Here's an exemplary configuration for this app. Adjust the values as you wish.

**Note:** For now, all time values have to be specified in 24H format and they should preferable not overlap as that can create weird behavior.

```yaml
daytime:
  module: daytime
  class: DayTime
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

### Configuration

key | optional | type | default | description
-- | -- | -- | -- | --
`module` | False | string | daytime | The module name of the app.
`class` | False | string | DayTime | The name of the python class.
`schedule` | False | list | | The schedule section used to define the time slots

#### Day configuration

key | optional | description
-- | -- | --
`morning` | False | Morning slot of the day
`day` | False | Day slot of the day
`evening` | False | Evening slot of the day
`night` | False | Night slot of the day

#### Slot configuration

key | optional | type | default | description
-- | -- | -- | -- | --
`type` | False | string | None | The type of slot time. Right now this can be set to `fixed` or `dynamic`.
`time` | False | string or list] | None | The time parameter of the slot configuration. If `type` is set to fixed, this should be a time string, i.e. '13:00', which specifies when this time slot begins. If `dynamic`it can be a list of multiple values, which can be either a normal time string or any of the keywords `sunrise` or `sunset`. If multiple values, the one happening first decides when this slot is triggered.
