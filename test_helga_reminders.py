# -*- coding: utf8 -*-
import datetime

import pytest
import pytz

from freezegun import freeze_time
from mock import Mock, patch

import helga_reminders as reminders


class TestDoReminder(object):

    def setup(self):
        reminders._scheduled.add(1)
        self.rec = {'channel': '#bots', 'message': 'some message'}
        self.now = datetime.datetime(day=11, month=12, year=2013)  # A wednesday
        self.client = Mock()

    @patch('helga_reminders.db')
    def test_do_reminder_simple(self, db):
        db.reminders.find_one.return_value = self.rec
        reminders._do_reminder(1, self.client)

        assert 1 not in reminders._scheduled
        db.reminders.remove.assert_called_with(1)
        self.client.msg.assert_called_with('#bots', 'some message')

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_do_reminder_reschedules_same_week(self, reactor, db):
        self.rec['when'] = self.now
        self.rec['repeat'] = [0, 2, 4]  # M, W, F
        db.reminders.find_one.return_value = self.rec

        with freeze_time(self.now):
            reminders._do_reminder(1, self.client)

        rec_upd = self.rec.copy()
        rec_upd['when'] = datetime.datetime(day=13, month=12, year=2013)

        db.reminders.save.assert_called_with(rec_upd)
        reactor.callLater.assert_called_with(48 * 3600, reminders._do_reminder, 1, self.client)

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_do_reminder_reschedules_next_week(self, reactor, db):
        self.rec['when'] = datetime.datetime(day=13, month=12, year=2013)
        self.rec['repeat'] = [0, 2, 4]  # M, W, F
        db.reminders.find_one.return_value = self.rec

        with freeze_time(self.rec['when']):
            reminders._do_reminder(1, self.client)

        rec_upd = self.rec.copy()
        rec_upd['when'] = datetime.datetime(day=16, month=12, year=2013)

        db.reminders.save.assert_called_with(rec_upd)
        reactor.callLater.assert_called_with(72 * 3600, reminders._do_reminder, 1, self.client)

    @patch('helga_reminders._scheduled')
    @patch('helga_reminders.db')
    def test_scheduled_discarded_with_no_record(self, db, scheduled):
        db.reminders.find_one.return_value = None
        reminders._do_reminder(1, Mock())
        scheduled.discard.assert_called_with(1)

    @patch('helga_reminders.db')
    def test_handles_unicode(self, db):
        client = Mock()
        snowman = u'☃'
        reminder = {
            'channel': snowman,
            'message': snowman,
        }
        db.reminders.find_one.return_value = reminder
        reminders._do_reminder(1, client)
        client.msg.assert_called_with(snowman, snowman)


class TestInReminder(object):

    def setup(self):
        reminders._scheduled.clear()
        self.client = Mock()
        self.now = datetime.datetime(day=13, month=12, year=2013)

    @pytest.mark.parametrize('channel', ['#foo', 'foo'])
    def test_in_reminder_for_different_channel(self, channel):
        with patch('helga_reminders.db') as db:
            with patch('helga_reminders.reactor'):
                db.reminders.insert.return_value = 1

                with freeze_time(self.now):
                    reminders.in_reminder(self.client, '#bots', 'me',
                                          ['12m', 'on', channel, 'this', 'is', 'the', 'message'])

                inserted = db.reminders.insert.call_args[0][0]
                assert inserted['channel'] == '#foo'
                assert inserted['message'] == 'this is the message'

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_in_reminder_for_minutes(self, reactor, db):
        db.reminders.insert.return_value = 1

        with freeze_time(self.now):
            reminders.in_reminder(self.client, '#bots', 'me', ['12m', 'this', 'is', 'the', 'message'])

        inserted = db.reminders.insert.call_args[0][0]

        assert inserted['message'] == 'this is the message'
        assert inserted['channel'] == '#bots'
        assert reactor.callLater.call_args[0] == (12 * 60, reminders._do_reminder, 1, self.client)

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_in_reminder_for_hours(self, reactor, db):
        db.reminders.insert.return_value = 1

        with freeze_time(self.now):
            reminders.in_reminder(self.client, '#bots', 'me', ['12h', 'this', 'is', 'the', 'message'])

        inserted = db.reminders.insert.call_args[0][0]

        assert inserted['message'] == 'this is the message'
        assert inserted['channel'] == '#bots'
        assert reactor.callLater.call_args[0] == (12 * 3600, reminders._do_reminder, 1, self.client)

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_in_reminder_for_days(self, reactor, db):
        db.reminders.insert.return_value = 1

        with freeze_time(self.now):
            reminders.in_reminder(self.client, '#bots', 'me', ['12d', 'this', 'is', 'the', 'message'])

        inserted = db.reminders.insert.call_args[0][0]

        assert inserted['message'] == 'this is the message'
        assert inserted['channel'] == '#bots'
        assert reactor.callLater.call_args[0] == (12 * 24 * 3600, reminders._do_reminder, 1, self.client)

    def test_in_reminder_for_unknown(self):
        resp = reminders.in_reminder(self.client, '#bots', 'me', ['12x', 'this', 'is', 'the', 'message'])
        assert resp.startswith("Sorry I didn't understand '12x'")


class TestAtReminder(object):

    def setup(self):
        self.client = Mock()
        self.now = datetime.datetime(day=11, month=12, year=2013, hour=12)
        self.past = datetime.datetime(day=9, month=12, year=2013, hour=12)
        self.future = datetime.datetime(day=13, month=12, year=2013, hour=12)

        self.tz = pytz.timezone('US/Eastern')

        reminders._scheduled.clear()

    @pytest.mark.parametrize('channel', ['#foo', 'foo'])
    def test_using_different_channel_and_with_repeat(self, channel):
        with patch('helga_reminders.db') as db:
            with patch('helga_reminders.reactor'):
                args = ['13:00', 'on', channel, 'test', 'message', 'repeat', 'MWF']
                db.reminders.insert.return_value = 1

                # Account for UTC difference
                with freeze_time(self.now + datetime.timedelta(hours=5)):
                    reminders.at_reminder(self.client, '#bots', 'me', args)

                rec = db.reminders.insert.call_args[0][0]
                assert rec['channel'] == '#foo'
                assert rec['message'] == 'test message'

    @pytest.mark.parametrize('channel', ['#foo', 'foo'])
    def test_using_different_channel(self, channel):
        with patch('helga_reminders.db') as db:
            with patch('helga_reminders.reactor'):
                args = ['13:00', 'on', channel, 'this is a message']
                db.reminders.insert.return_value = 1

                # Account for UTC difference
                with freeze_time(self.now + datetime.timedelta(hours=5)):
                    reminders.at_reminder(self.client, '#bots', 'me', args)

                rec = db.reminders.insert.call_args[0][0]
                assert rec['channel'] == '#foo'
                assert rec['message'] == 'this is a message'

    @pytest.mark.parametrize('channel', ['#foo', 'foo'])
    def test_using_different_channel_when_timezone_present(self, channel):
        with patch('helga_reminders.db') as db:
            with patch('helga_reminders.reactor'):
                args = ['13:00', 'EST', 'on', '#foo', 'this is a message']
                db.reminders.insert.return_value = 1

                # Account for UTC difference
                with freeze_time(self.now + datetime.timedelta(hours=5)):
                    reminders.at_reminder(self.client, '#bots', 'me', args)

                rec = db.reminders.insert.call_args[0][0]
                assert rec['channel'] == '#foo'
                assert rec['message'] == 'this is a message'

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_no_tz_no_repeat_in_future(self, reactor, db):
        args = ['13:00', 'this is a message']
        db.reminders.insert.return_value = 1

        # Account for UTC difference
        with freeze_time(self.now + datetime.timedelta(hours=5)):
            reminders.at_reminder(self.client, '#bots', 'me', args)

        rec = db.reminders.insert.call_args[0][0]
        expect = self.now + datetime.timedelta(hours=1)

        # 'when' will be stored as UTC timestamp
        when = rec['when'].astimezone(self.tz).replace(tzinfo=None)

        assert 'repeat' not in rec
        assert when == expect
        assert rec['channel'] == '#bots'
        assert rec['message'] == 'this is a message'
        reactor.callLater.assert_called_with(1*3600, reminders._do_reminder, 1, self.client)

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_no_tz_no_repeat_in_past(self, reactor, db):
        args = ['6:00', 'this is a message']
        db.reminders.insert.return_value = 1

        # Account for UTC difference
        with freeze_time(self.now + datetime.timedelta(hours=5)):
            reminders.at_reminder(self.client, '#bots', 'me', args)

        rec = db.reminders.insert.call_args[0][0]
        expect = self.now + datetime.timedelta(hours=18)

        # 'when' will be stored as UTC timestamp
        when = rec['when'].astimezone(self.tz).replace(tzinfo=None)

        assert 'repeat' not in rec
        assert when == expect
        assert rec['channel'] == '#bots'
        assert rec['message'] == 'this is a message'
        reactor.callLater.assert_called_with(18*3600, reminders._do_reminder, 1, self.client)

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_tz_no_repeat_in_future(self, reactor, db):
        args = ['13:00', 'US/Central', 'this is a message']
        db.reminders.insert.return_value = 1

        # Account for UTC difference
        with freeze_time(self.now + datetime.timedelta(hours=6)):
            reminders.at_reminder(self.client, '#bots', 'me', args)

        rec = db.reminders.insert.call_args[0][0]
        expect = self.now + datetime.timedelta(hours=1)

        # 'when' will be stored as UTC timestamp
        when = rec['when'].astimezone(pytz.timezone('US/Central')).replace(tzinfo=None)

        assert 'repeat' not in rec
        assert when == expect
        assert rec['channel'] == '#bots'
        assert rec['message'] == 'this is a message'
        reactor.callLater.assert_called_with(1*3600, reminders._do_reminder, 1, self.client)

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_tz_no_repeat_in_past(self, reactor, db):
        args = ['6:00', 'US/Central', 'this is a message']
        db.reminders.insert.return_value = 1

        # Account for UTC difference
        with freeze_time(self.now + datetime.timedelta(hours=6)):
            reminders.at_reminder(self.client, '#bots', 'me', args)

        rec = db.reminders.insert.call_args[0][0]
        expect = self.now + datetime.timedelta(hours=18)

        # 'when' will be stored as UTC timestamp
        when = rec['when'].astimezone(pytz.timezone('US/Central')).replace(tzinfo=None)

        assert 'repeat' not in rec
        assert when == expect
        assert rec['channel'] == '#bots'
        assert rec['message'] == 'this is a message'
        reactor.callLater.assert_called_with(18*3600, reminders._do_reminder, 1, self.client)

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_tz_repeat_in_future(self, reactor, db):
        args = ['13:00', 'US/Central', 'this is a message', 'repeat', 'MWF']
        db.reminders.insert.return_value = 1

        # Account for UTC difference
        with freeze_time(self.now + datetime.timedelta(hours=6)):
            reminders.at_reminder(self.client, '#bots', 'me', args)

        rec = db.reminders.insert.call_args[0][0]
        expect = self.now + datetime.timedelta(hours=1)

        # 'when' will be stored as UTC timestamp
        when = rec['when'].astimezone(pytz.timezone('US/Central')).replace(tzinfo=None)

        assert when == expect
        assert rec['channel'] == '#bots'
        assert rec['message'] == 'this is a message'
        assert rec['repeat'] == [0, 2, 4]
        reactor.callLater.assert_called_with(1*3600, reminders._do_reminder, 1, self.client)

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_tz_repeat_in_past(self, reactor, db):
        args = ['6:00', 'US/Central', 'this is a message', 'repeat', 'MWF']
        db.reminders.insert.return_value = 1

        # Account for UTC difference
        with freeze_time(self.now + datetime.timedelta(hours=6)):
            reminders.at_reminder(self.client, '#bots', 'me', args)

        rec = db.reminders.insert.call_args[0][0]
        expect = self.now + datetime.timedelta(hours=42)  # We expect it to be on Friday now

        # 'when' will be stored as UTC timestamp
        when = rec['when'].astimezone(pytz.timezone('US/Central')).replace(tzinfo=None)

        assert when == expect
        assert rec['channel'] == '#bots'
        assert rec['message'] == 'this is a message'
        assert rec['repeat'] == [0, 2, 4]
        reactor.callLater.assert_called_with(42*3600, reminders._do_reminder, 1, self.client)

    @patch('helga_reminders.db')
    @patch('helga_reminders.reactor')
    def test_invalid_days_returns_warning(self, reactor, db):
        # Invalid chars
        args = ['6:00', 'US/Central', 'this is a message', 'repeat', 'XYZ']
        assert "I didn't understand" in reminders.at_reminder(self.client, '#bots', 'me', args)
        assert not db.reminders.insert.called
        assert not reactor.callLater.called

        # No chars
        args = ['6:00', 'US/Central', 'this is a message', 'repeat', '']
        assert "I didn't understand" in reminders.at_reminder(self.client, '#bots', 'me', args)
        assert not db.reminders.insert.called
        assert not reactor.callLater.called


class TestReadableTime(object):

    def test_readable_time_delta_minutes_only(self):
        ret = reminders.readable_time_delta(610)
        assert ret == '10 minutes'

    def test_readable_time_delta_hours_and_minutes(self):
        ret = reminders.readable_time_delta((3 * 3600) + 610)
        assert ret == '3 hours and 10 minutes'

    def test_readable_time_delta_days_hours_and_minutes(self):
        ret = reminders.readable_time_delta((8 * 86400) + (3 * 3600) + 610)
        assert ret == '8 days, 3 hours and 10 minutes'

    def test_readable_time_delta_singular_minutes(self):
        ret = reminders.readable_time_delta(65)
        assert ret == '1 minute'

    def test_readable_time_delta_singular_hours_and_minutes(self):
        ret = reminders.readable_time_delta((1 * 3600) + 65)
        assert ret == '1 hour and 1 minute'

    def test_readable_time_delta_singular_days_hours_and_minutes(self):
        ret = reminders.readable_time_delta((1 * 86400) + (1 * 3600) + 65)
        assert ret == '1 day, 1 hour and 1 minute'


class TestListReminders(object):

    def setup(self):
        self.rec = {
            '_id': '1234567890abcdefg',
            'when': datetime.datetime(year=2013, month=12, day=11, hour=13, minute=15, tzinfo=pytz.UTC),
            'message': 'Standup Time!',
        }

    @patch('helga_reminders.list_reminders')
    def test_list_reponds_via_privmsg(self, list_reminders):
        client = Mock()

        assert reminders.reminders(client, '#all', 'sduncan', 'reminders list', 'reminders', ['list']) is None
        client.me.assert_called_with('#all', 'whispers to sduncan')
        list_reminders.assert_called_with(client, 'sduncan', '#all')

    @patch('helga_reminders.list_reminders')
    def test_list_reponds_via_privmsg_for_specific_chan(self, list_reminders):
        client = Mock()

        assert reminders.reminders(client, '#all', 'sduncan', 'reminders list #bots',
                                   'reminders', ['list', '#bots']) is None
        client.me.assert_called_with('#all', 'whispers to sduncan')
        list_reminders.assert_called_with(client, 'sduncan', '#bots')

    @patch('helga_reminders.db')
    def test_list_no_results(self, db):
        client = Mock()
        db.reminders.find.return_value = []
        reminders.list_reminders(client, 'sduncan', '#bots')

        client.msg.assert_called_with('sduncan', "There are no reminders for channel: #bots")

    @patch('helga_reminders.db')
    def test_simple(self, db):
        client = Mock()
        client.msg = client

        db.reminders.find.return_value = [self.rec]
        reminders.list_reminders(client, 'sduncan', '#bots')

        client.msg.assert_called_with(
            'sduncan',
            "sduncan, here are the reminders for channel: #bots\n"
            "[{0}] At 12/11/13 13:15 UTC: 'Standup Time!'".format(self.rec['_id'])
        )

    @patch('helga_reminders.db')
    def test_with_repeats(self, db):
        client = Mock()
        client.msg = client

        self.rec['repeat'] = [0, 2, 4]
        db.reminders.find.return_value = [self.rec]
        reminders.list_reminders(client, 'sduncan', '#bots')

        client.msg.assert_called_with(
            'sduncan',
            "sduncan, here are the reminders for channel: #bots\n"
            "[{0}] At 12/11/13 13:15 UTC: 'Standup Time!' (Repeat every M,W,F)".format(self.rec['_id'])
        )


class TestInitReminders(object):

    @patch('helga_reminders.reactor')
    @patch('helga_reminders.db')
    def test_ignores_scheduled_reminder(self, db, reactor):
        records = [
            {
                '_id': 1234567890,
                'when': datetime.datetime(day=13, month=12, year=2013)
            },
        ]
        db.reminders.find.return_value = records

        with patch.object(reminders, '_scheduled', set([1234567890])):
            reminders.init_reminders(Mock())
            assert not reactor.callLater.called

    @patch('helga_reminders.reactor')
    @patch('helga_reminders.db')
    def test_schedules_reminder(self, db, reactor):
        records = [
            {
                '_id': 1234567890,
                'when': datetime.datetime(day=13, month=12, year=2013, tzinfo=pytz.UTC)
            }
        ]
        db.reminders.find.return_value = records

        with freeze_time(records[0]['when']):
            client = Mock()
            with patch.object(reminders, '_scheduled', set()):
                reminders.init_reminders(client)
                assert 1234567890 in reminders._scheduled
                reactor.callLater.assert_called_with(0, reminders._do_reminder, 1234567890, client)

    @patch('helga_reminders.db')
    def test_with_stale_reminder(self, db):
        records = [
            {
                '_id': 1234567890,
                'when': datetime.datetime(day=13, month=12, year=2013)
            }
        ]
        db.reminders.find.return_value = records

        with freeze_time(records[0]['when'] + datetime.timedelta(days=1)):
            client = Mock()
            with patch.object(reminders, '_scheduled', set()):
                reminders.init_reminders(client)
                assert 1234567890 not in reminders._scheduled
                db.reminders.remove.assert_called_with(1234567890)

    @patch('helga_reminders.reactor')
    @patch('helga_reminders.db')
    def test_with_late_reminder(self, db, reactor):
        records = [
            {
                '_id': 1234567890,
                'when': datetime.datetime(day=13, month=12, year=2013)
            }
        ]
        db.reminders.find.return_value = records

        with freeze_time(records[0]['when'] + datetime.timedelta(seconds=60)):
            client = Mock()
            with patch.object(reminders, '_scheduled', set()):
                reminders.init_reminders(client)
                assert 1234567890 in reminders._scheduled
                reactor.callLater.assert_called_with(0, reminders._do_reminder, 1234567890, client)

    @patch('helga_reminders.reactor')
    @patch('helga_reminders.db')
    def test_with_repeated_reminder(self, db, reactor):
        records = [
            {
                '_id': 1234567890,
                'when': datetime.datetime(day=13, month=12, year=2013),
                'repeat': range(7),
            }
        ]
        db.reminders.find.return_value = records

        with freeze_time(records[0]['when'] + datetime.timedelta(seconds=300)):
            client = Mock()
            with patch.object(reminders, '_scheduled', set()):
                reminders.init_reminders(client)
                assert 1234567890 in reminders._scheduled
                # It's 300 seconds, late. Should be 1 day from that point
                reactor.callLater.assert_called_with(86400 - 300, reminders._do_reminder, 1234567890, client)
                db.reminders.save.assert_called_with({
                    '_id': 1234567890,
                    'when': datetime.datetime(day=14, month=12, year=2013),
                    'repeat': range(7),
                })


class TestNextOccurrence(object):

    def test_next_occurrence(self):
        reminder = {
            '_id': 1,
            # Start on a wednesday
            'when': datetime.datetime(day=13, month=8, year=2014),
        }

        past = (0, 5)  # Expect 5 days in the future
        today = (2, 7)  # Expect 1 week in the future
        future = (5, 3)  # Expect 3 days in the future

        with freeze_time(reminder['when']):
            for repeat, expect_delta in (past, today, future):
                reminder['repeat'] = [repeat]
                next_time, next_delta = reminders.next_occurrence(reminder)
                assert expect_delta == next_delta
                assert next_time == reminder['when'] + datetime.timedelta(days=expect_delta)

    @patch('helga_reminders._scheduled')
    @patch('__builtin__.next')
    def test_when_no_next_dow(self, _next, scheduled):
        _next.side_effect = StopIteration

        reminder = {
            '_id': 1,
            'when': datetime.datetime(day=13, month=8, year=2014),
            'repeat': range(7),
        }

        assert reminders.next_occurrence(reminder) is None
        scheduled.discard.assert_called_with(1)


class TestDeleteReminder(object):

    @patch('helga_reminders.db')
    def test_no_found_record(self, db):
        id = '54f529958973817f30dead5a'
        db.reminders.find_one.return_value = None
        retval = reminders.delete_reminder('#bots', id)
        assert retval == "No reminder found with id '{0}'".format(id)

    @patch('helga_reminders.db')
    def test_deletes_record(self, db):
        id = '54f529958973817f30dead5a'
        db.reminders.find_one.return_value = {'_id': id}
        reminders.delete_reminder('#bots', id)
        db.reminders.remove.assert_called_with(id)

    def test_invalid_id(self):
        resp = reminders.delete_reminder('#bots', 'xyz')
        assert resp == "Invalid ID format 'xyz'"


class TestReminderSubcommand(object):

    @patch('helga_reminders.in_reminder')
    def test_in_reminder(self, in_reminder):
        client = Mock()
        reminders.reminders(client, '#bots', 'me', 'message', 'in', ['args'])
        in_reminder.assert_called_with(client, '#bots', 'me', ['args'])

    @patch('helga_reminders.at_reminder')
    def test_at_reminder(self, at_reminder):
        client = Mock()
        reminders.reminders(client, '#bots', 'me', 'message', 'at', ['args'])
        at_reminder.assert_called_with(client, '#bots', 'me', ['args'])

    @patch('helga_reminders.list_reminders')
    def test_list_reminders(self, list_reminder):
        client = Mock()
        reminders.reminders(client, '#bots', 'me', 'message', 'reminders', ['list'])
        list_reminder.assert_called_with(client, 'me', '#bots')
        client.me.assert_called_with('#bots', 'whispers to me')

    @patch('helga_reminders.list_reminders')
    def test_list_reminders_with_channel(self, list_reminder):
        client = Mock()
        reminders.reminders(client, '#bots', 'me', 'message', 'reminders', ['list', '#blah'])
        list_reminder.assert_called_with(client, 'me', '#blah')
        client.me.assert_called_with('#bots', 'whispers to me')

    @patch('helga_reminders.delete_reminder')
    def test_delete_reminder(self, delete_reminder):
        client = Mock()
        reminders.reminders(client, '#bots', 'me', 'message', 'reminders', ['delete', '1'])
        delete_reminder.assert_called_with('#bots', '1')
