helga-reminders
===============

A command plugin for scheduling one time or recurring reminders. Usage::

    helga (in ##(m|h|d) [on <channel>] <message>|at <HH>:<MM> [<timezone>] [on <channel>] <message> [repeat <days_of_week>]|reminders list [channel]|reminders delete <hash>)

Each reminder setting command acts as follows:

``in ##(m|h|d) [on <channel>] <message>``
    Schedule a message to appear in some number of minutes, hours, or days on the current channel.
    Optionally, ``on <channel>`` will set this reminder to occur on the specified channel. This is useful
    for setting channel reminders via a private message. For example::

        <sduncan> !in 8h on #work QUITTING TIME!

``at <HH>:<MM> [<timezone>] [on <channel>] <message> [repeat <days_of_week>]``
    Schedule a message to appear at a specific time in the future. ``on <channel>`` will set this reminder
    to occur on the specified channel, which is useful for setting channel reminders via a private message.
    If not specified, the default timezone is assumed to be UTC, otherwise a timezone such as
    'US/Eastern' that can be recognized by pytz can be specified. Times must be in 24h clock format.
    For example::

        <sduncan> !at 17:00 US/Eastern on #work QUITTING TIME!

    You can also set these reminders to occur at repeating intervals in the future by specifying ``repeat``
    followed by a string of days of the week. For example::

        <sduncan> !at 17:00 US/Eastern on #work QUITTING TIME! repeat MTuWThF

    Valid days of the week are:

    * ``Su``: Sunday
    * ``M``: Monday
    * ``Tu``: Tuesday
    * ``W``: Wednesday
    * ``Th``: Thursday
    * ``F``: Friday
    * ``Sa``: Saturday

``reminders list [channel]``
    List all of the reminders set to occur on the current channel. Specifying a channel name will list
    all the reminders set to occur on that channel.

``reminders delete <hash>``
    Delete a stored reminder with the given hash. Reminder hashes can be obtained using the
    ``reminders list`` command.

.. important::

    This plugin requires database access


License
-------

Copyright (c) 2015 Shaun Duncan

Licensed under an `MIT`_ license.

.. _`MIT`: https://github.com/shaunduncan/helga-reminders/blob/master/LICENSE
