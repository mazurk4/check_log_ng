#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Unit test for check_log_ng"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import unittest
import warnings
import os
import io
import time
import datetime
import subprocess
from check_log_ng import LogChecker


class LogCheckerTestCase(unittest.TestCase):

    """Unit test."""

    # Class constant
    MESSAGE_OK = "OK - No matches found."
    MESSAGE_WARNING_ONE = "WARNING: Found 1 lines (limit=1/0): {0} at {1}"
    MESSAGE_WARNING_TWO = "WARNING: Found 2 lines (limit=1/0): {0},{1} at {2}"
    MESSAGE_WARNING_TWO_IN_TWO_FILES = (
        "WARNING: Found 2 lines (limit=1/0): {0} at {1},{2} at {3}")
    MESSAGE_CRITICAL_ONE = "CRITICAL: Critical Found 1 lines: {0} at {1}"
    MESSAGE_UNKNOWN_LOCK_TIMEOUT = (
        "UNKNOWN: Lock timeout. Another process is running.")

    # Class variablesex
    BASEDIR = None
    TESTDIR = None
    LOGDIR = None
    SEEKDIR = None

    @classmethod
    def setUpClass(cls):
        cls.BASEDIR = os.getcwd()
        cls.TESTDIR = os.path.join(cls.BASEDIR, 'test')
        cls.LOGDIR = os.path.join(cls.TESTDIR, 'log')
        cls.SEEKDIR = os.path.join(cls.TESTDIR, 'seek')
        if not os.path.isdir(cls.TESTDIR):
            os.mkdir(cls.TESTDIR)
        if not os.path.isdir(cls.LOGDIR):
            os.mkdir(cls.LOGDIR)
        if not os.path.isdir(cls.SEEKDIR):
            os.mkdir(cls.SEEKDIR)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.LOGDIR):
            os.removedirs(cls.LOGDIR)
        if os.path.exists(cls.SEEKDIR):
            os.removedirs(cls.SEEKDIR)
        if os.path.exists(cls.TESTDIR):
            os.removedirs(cls.TESTDIR)

    def setUp(self):
        # log files
        self.logfile = os.path.join(self.LOGDIR, 'testlog')
        self.logfile1 = os.path.join(self.LOGDIR, 'testlog.1')
        self.logfile2 = os.path.join(self.LOGDIR, 'testlog.2')
        self.logfile_pattern = os.path.join(self.LOGDIR, 'testlog*')

        # seek files
        self.tag1 = 'tag1'
        self.tag2 = 'tag2'
        self.seekfile = os.path.join(self.SEEKDIR, 'testlog.seek')
        self.seekfile1 = LogChecker.get_seekfile(
            self.logfile_pattern, self.SEEKDIR, self.logfile1)
        self.seekfile2 = LogChecker.get_seekfile(
            self.logfile_pattern, self.SEEKDIR, self.logfile2)

        # cache file and lock file
        prefix_datafile = LogChecker.get_prefix_datafile('', self.SEEKDIR)
        self.cachefile = "".join([prefix_datafile, LogChecker.SUFFIX_CACHE])
        self.lockfile = "".join([prefix_datafile, LogChecker.SUFFIX_LOCK])

        # configuration
        self.config = {
            "logformat": LogChecker.FORMAT_SYSLOG,
            "pattern_list": [],
            "critical_pattern_list": [],
            "negpattern_list": [],
            "critical_negpattern_list": [],
            "case_insensitive": False,
            "encoding": "utf-8",
            "warning": 1,
            "critical": 0,
            "nodiff_warn": False,
            "nodiff_crit": False,
            "trace_inode": False,
            "multiline": False,
            "scantime": 86400,
            "expiration": 691200,
            "cache": False,
            "cachetime": 60,
            "lock_timeout": 3
        }

    def tearDown(self):
        # remove seek files and log files.
        if os.path.exists(self.seekfile):
            os.unlink(self.seekfile)
        for logfile in [self.logfile, self.logfile1, self.logfile2]:
            if not os.path.exists(logfile):
                continue
            for trace_inode in [True, False]:
                seekfile = LogChecker.get_seekfile(
                    self.logfile_pattern, self.SEEKDIR, logfile,
                    trace_inode=trace_inode)
                if os.path.exists(seekfile):
                    os.unlink(seekfile)
            for seekfile_tag in [self.tag1, self.tag2]:
                seekfile = LogChecker.get_seekfile(
                    self.logfile_pattern, self.SEEKDIR, logfile,
                    seekfile_tag=seekfile_tag)
                if os.path.exists(seekfile):
                    os.unlink(seekfile)
            os.unlink(logfile)

        # remove cache file and lock file.
        if os.path.exists(self.cachefile):
            os.unlink(self.cachefile)
        if os.path.exists(self.lockfile):
            os.unlink(self.lockfile)

    def test_format(self):
        """--format option
        """
        self.config["logformat"] = r"^(\[%a %b %d %T %Y\] \[\S+\]) (.*)$"
        self.config["pattern_list"] = ["ERROR"]
        log = LogChecker(self.config)

        # [Thu Dec 05 12:34:50 2013] [error] ERROR
        line = self._make_customized_line(
            self._get_customized_timestamp(), "error", "ERROR")
        self._write_customized_logfile(self.logfile, line)
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line, self.logfile))

    def test_pattern(self):
        """--pattern option
        """
        self.config["pattern_list"] = ["ERROR"]
        log = LogChecker(self.config)

        # 1 line matched
        # Dec  5 12:34:50 hostname test: ERROR
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line1)
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line1, self.logfile))

        # 2 lines matched
        # Dec  5 12:34:50 hostname test: ERROR1
        # Dec  5 12:34:50 hostname test: ERROR2
        line2 = self._make_line(self._get_timestamp(), "test", "ERROR1")
        line3 = self._make_line(self._get_timestamp(), "test", "ERROR2")
        self._write_logfile(self.logfile, [line2, line3])
        log.clear_state()
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_TWO.format(line2, line3, self.logfile))

        # no line matched
        # Dec  5 12:34:50 hostname noop: NOOP
        line4 = self._make_line(self._get_timestamp(), "noop", "NOOP")
        self._write_logfile(self.logfile, line4)
        log.clear_state()
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_OK)
        self.assertEqual(log.get_message(), self.MESSAGE_OK)

    def test_critical_pattern(self):
        """--critical-pattern option
        """
        self.config["critical_pattern_list"] = ["FATAL"]
        log = LogChecker(self.config)

        # Dec  5 12:34:50 hostname test: FATAL
        line = self._make_line(self._get_timestamp(), "test", "FATAL")
        self._write_logfile(self.logfile, line)
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_CRITICAL)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_CRITICAL_ONE.format(line, self.logfile))

    def test_negpattern(self):
        """--negpattern option
        """
        self.config["pattern_list"] = ["ERROR"]
        self.config["critical_pattern_list"] = ["FATAL"]
        self.config["negpattern_list"] = ["IGNORE"]
        log = LogChecker(self.config)

        # check --pattern
        # Dec  5 12:34:50 hostname test: ERROR IGNORE
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR IGNORE")
        self._write_logfile(self.logfile, line1)
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_OK)
        self.assertEqual(log.get_message(), self.MESSAGE_OK)

        # check --critical-pattern
        # Dec  5 12:34:50 hostname test: FATAL IGNORE
        line2 = self._make_line(self._get_timestamp(), "test", "FATAL IGNORE")
        self._write_logfile(self.logfile, line2)
        log.clear_state()
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_CRITICAL)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_CRITICAL_ONE.format(line2, self.logfile))

    def test_critical_negpattern(self):
        """--critical-negpattern option
        """
        self.config["pattern_list"] = ["ERROR"]
        self.config["critical_pattern_list"] = ["FATAL"]
        self.config["critical_negpattern_list"] = ["IGNORE"]
        log = LogChecker(self.config)

        # check --pattern and --critical-negpattern
        # Dec  5 12:34:50 hostname test: ERROR IGNORE
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR IGNORE")
        self._write_logfile(self.logfile, line1)
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_OK)
        self.assertEqual(log.get_message(), self.MESSAGE_OK)

        # check --critical-pattern and --ciritical-negpattern
        # Dec  5 12:34:50 hostname test: FATAL IGNORE
        line2 = self._make_line(self._get_timestamp(), "test", "FATAL IGNORE")
        self._write_logfile(self.logfile, line2)
        log.clear_state()
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_OK)
        self.assertEqual(log.get_message(), self.MESSAGE_OK)

        # check --pattern, --critical-pattern and --critical-negpattern
        # Dec  5 12:34:50 hostname test: ERROR FATAL IGNORE
        line3 = self._make_line(
            self._get_timestamp(), "test", "ERROR FATAL IGNORE")
        self._write_logfile(self.logfile, line3)
        log.clear_state()
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_OK)
        self.assertEqual(log.get_message(), self.MESSAGE_OK)

    def test_case_insensitive(self):
        """--case-insensitive option
        """
        self.config["pattern_list"] = ["error"]
        self.config["critical_pattern_list"] = ["fatal"]
        self.config["negpattern_list"] = ["ignore"]
        self.config["case_insensitive"] = True
        log = LogChecker(self.config)

        # check --pattern
        # Dec  5 12:34:50 hostname test: ERROR
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line1)
        log.clear_state()
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line1, self.logfile))

        # check --critical-pattern
        # Dec  5 12:34:50 hostname test: FATAL
        line2 = self._make_line(self._get_timestamp(), "test", "FATAL")
        self._write_logfile(self.logfile, line2)
        log.clear_state()
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_CRITICAL)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_CRITICAL_ONE.format(line2, self.logfile))

        # check --pattern and --negpattern
        # Dec  5 12:34:50 hostname test: ERROR ERROR IGNORE
        line3 = self._make_line(self._get_timestamp(), "test", "ERROR IGNORE")
        self._write_logfile(self.logfile, line3)
        log.clear_state()
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_OK)
        self.assertEqual(log.get_message(), self.MESSAGE_OK)

    def test_encoding(self):
        """--pattern and --encoding
        """
        self.config["pattern_list"] = ["エラー"]
        self.config["encoding"] = "EUC-JP"
        log = LogChecker(self.config)

        # Dec  5 12:34:50 hostname test: エラー
        line = self._make_line(self._get_timestamp(), "test", "エラー")
        self._write_logfile(self.logfile, line, encoding='EUC-JP')
        log.clear_state()
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line, self.logfile))

    def test_multiline(self):
        """--multiline
        """
        self.config["pattern_list"] = ["ERROR1.*ERROR2"]
        self.config["negpattern_list"] = ["IGNORE"]
        self.config["multiline"] = True
        log = LogChecker(self.config)

        # check --pattern, --multiline
        # Dec  5 12:34:50 hostname test: ERROR1
        # Dec  5 12:34:50 hostname test: ERROR2
        timestamp = self._get_timestamp()
        lines = []
        messages = ["ERROR1", "ERROR2"]
        for message in messages:
            lines.append(self._make_line(timestamp, "test", message))
        self._write_logfile(self.logfile, lines)
        log.clear_state()
        log.check_log(self.logfile, self.seekfile)

        # detected line: Dec  5 12:34:50 hostname test: ERROR1 ERROR2
        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(
                lines[0] + " " + messages[1], self.logfile))

        # check --pattern, --negpattern and --multiline
        # Dec  5 12:34:50 hostname test: ERROR
        # Dec  5 12:34:50 hostname test: ERROR IGNORE
        timestamp = self._get_timestamp()
        lines = []
        messages = ["ERROR", "ERROR IGNORE"]
        for message in messages:
            lines.append(self._make_line(timestamp, "test", message))
        self._write_logfile(self.logfile, lines)
        log.clear_state()
        log.check_log(self.logfile, self.seekfile)

        # detected line: Dec  5 12:34:50 hostname test: ERROR ERROR IGNORE
        self.assertEqual(log.get_state(), LogChecker.STATE_OK)
        self.assertEqual(log.get_message(), self.MESSAGE_OK)

    def test_logfile(self):
        """--logfile option
        """
        self.config["pattern_list"] = ["ERROR"]
        log = LogChecker(self.config)

        # check -logfile option with wild card '*'
        # Dec  5 12:34:50 hostname test: ERROR
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile1, line1)

        # Dec  5 12:34:50 hostname test: ERROR
        line2 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile2, line2)
        log.clear_state()
        log.check_log_multi(self.logfile_pattern, self.SEEKDIR)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_TWO_IN_TWO_FILES.format(
                line1, self.logfile1, line2, self.logfile2))

        # --logfile option with multiple filenames
        # Dec  5 12:34:50 hostname test: ERROR
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile1, line1)

        # Dec  5 12:34:50 hostname test: ERROR
        line2 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile2, line2)
        logfile_pattern = "{0} {1}".format(self.logfile1, self.logfile2)
        log.clear_state()
        log.check_log_multi(logfile_pattern, self.SEEKDIR)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_TWO_IN_TWO_FILES.format(
                line1, self.logfile1, line2, self.logfile2))

    def test_trace_inode(self):
        """--trace_inode
        """
        self.config["pattern_list"] = ["ERROR"]
        self.config["trace_inode"] = True
        log = LogChecker(self.config)

        # within expiration
        # create logfile
        # Dec  5 12:34:50 hostname test: ERROR
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line1)

        # create seekfile of logfile
        log.check_log_multi(self.logfile_pattern, self.SEEKDIR)
        seekfile_1 = LogChecker.get_seekfile(
            self.logfile_pattern, self.SEEKDIR, self.logfile, trace_inode=True)

        # update logfile
        # Dec  5 12:34:51 hostname test: ERROR
        line2 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line2)

        # log rotation
        os.rename(self.logfile, self.logfile1)

        # create a new logfile
        # Dec  5 12:34:52 hostname noop: NOOP
        line3 = self._make_line(self._get_timestamp(), "noop", "NOOP")
        self._write_logfile(self.logfile, line3)

        # create seekfile of logfile
        log.clear_state()
        log.check_log_multi(self.logfile_pattern, self.SEEKDIR)
        seekfile_2 = LogChecker.get_seekfile(
            self.logfile_pattern, self.SEEKDIR, self.logfile, trace_inode=True)
        seekfile1_2 = LogChecker.get_seekfile(
            self.logfile_pattern, self.SEEKDIR, self.logfile1,
            trace_inode=True)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line2, self.logfile1))
        self.assertEqual(seekfile_1, seekfile1_2)
        self.assertTrue(os.path.exists(seekfile_2))
        self.assertTrue(os.path.exists(seekfile1_2))

    def test_scantime(self):
        """--scantime option
        """
        self.config["pattern_list"] = ["ERROR"]
        self.config["scantime"] = 2
        log = LogChecker(self.config)

        # within scantime.
        # Dec  5 12:34:50 hostname test: ERROR
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile1, line1)
        log.clear_state()
        log.check_log_multi(self.logfile_pattern, self.SEEKDIR)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line1, self.logfile1))

        # over scantime
        # Dec  5 12:34:50 hostname test: ERROR
        line2 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile1, line2)
        time.sleep(4)
        log.clear_state()
        log.check_log_multi(self.logfile_pattern, self.SEEKDIR)

        self.assertEqual(log.get_state(), LogChecker.STATE_OK)
        self.assertEqual(log.get_message(), self.MESSAGE_OK)

        # multiple logfiles.
        # Dec  5 12:34:50 hostname test: ERROR
        line3 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile1, line3)
        time.sleep(4)

        # Dec  5 12:34:54 hostname test: ERROR
        line4 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile2, line4)

        # logfile1 should be older than spantime. Therefore, don't scan it.
        log.clear_state()
        log.check_log_multi(self.logfile_pattern, self.SEEKDIR)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line4, self.logfile2))

    def test_remove_seekfile(self):
        """--expiration and --remove-seekfile options
        """
        self.config["pattern_list"] = ["ERROR"]
        self.config["scantime"] = 2
        self.config["expiration"] = 4
        log = LogChecker(self.config)

        # within expiration
        # Dec  5 12:34:50 hostname test: ERROR
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile1, line1)

        log.check_log_multi(
            self.logfile_pattern, self.SEEKDIR, remove_seekfile=True)
        time.sleep(2)

        # Dec  5 12:34:54 hostname test: ERROR
        line2 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile2, line2)

        # seek file of logfile1 should not be purged.
        log.clear_state()
        log.check_log_multi(
            self.logfile_pattern, self.SEEKDIR, remove_seekfile=True)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line2, self.logfile2))
        self.assertTrue(os.path.exists(self.seekfile1))
        self.assertTrue(os.path.exists(self.seekfile2))

        # over expiration
        # Dec  5 12:34:50 hostname test: ERROR
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile1, line1)

        log.check_log_multi(
            self.logfile_pattern, self.SEEKDIR, remove_seekfile=True)
        time.sleep(6)

        # Dec  5 12:34:54 hostname test: ERROR
        line2 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile2, line2)

        # seek file of logfile1 should be purged.
        log.clear_state()
        log.check_log_multi(
            self.logfile_pattern, self.SEEKDIR, remove_seekfile=True)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line2, self.logfile2))
        self.assertFalse(os.path.exists(self.seekfile1))
        self.assertTrue(os.path.exists(self.seekfile2))

    def test_remove_seekfile_inode(self):
        """--trace_inode, --expiration and --remove-seekfile options
        """
        self.config["pattern_list"] = ["ERROR"]
        self.config["trace_inode"] = True
        self.config["scantime"] = 2
        self.config["expiration"] = 3
        log = LogChecker(self.config)

        # create logfile
        # Dec  5 12:34:50 hostname test: ERROR
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line1)

        # log rotation
        os.rename(self.logfile, self.logfile1)

        # create new logfile
        # Dec  5 12:34:50 hostname test: ERROR
        line2 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line2)

        # do check_log_multi, and create seekfile and seekfile1
        log.clear_state()
        log.check_log_multi(
            self.logfile_pattern, self.SEEKDIR, remove_seekfile=True)
        seekfile_1 = LogChecker.get_seekfile(
            self.logfile_pattern, self.SEEKDIR, self.logfile,
            trace_inode=True)
        seekfile1_1 = LogChecker.get_seekfile(
            self.logfile_pattern, self.SEEKDIR, self.logfile1,
            trace_inode=True)
        time.sleep(4)

        # update logfile
        # Dec  5 12:34:54 hostname test: ERROR
        line3 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line3)

        # log rotation, purge old logfile2
        os.rename(self.logfile1, self.logfile2)
        os.rename(self.logfile, self.logfile1)

        # seek file of old logfile1 should be purged.
        log.clear_state()
        log.check_log_multi(
            self.logfile_pattern, self.SEEKDIR, remove_seekfile=True)
        seekfile1_2 = LogChecker.get_seekfile(
            self.logfile_pattern, self.SEEKDIR, self.logfile1,
            trace_inode=True)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line3, self.logfile1))
        self.assertEqual(seekfile_1, seekfile1_2)
        self.assertFalse(os.path.exists(seekfile1_1))
        self.assertTrue(os.path.exists(seekfile1_2))

    def test_replace_pipe_symbol(self):
        """replace pipe symbol
        """
        line = "Dec | 5 12:34:56 hostname test: ERROR"
        self.config["pattern_list"] = ["ERROR"]
        log = LogChecker(self.config)

        # Dec  5 12:34:50 hostname test: ERROR |
        line = self._make_line(self._get_timestamp(), "test", "ERROR |")
        self._write_logfile(self.logfile, line)
        log.check_log(self.logfile, self.seekfile)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(
                line.replace("|", "(pipe)"), self.logfile))

    def test_seekfile_tag(self):
        """--seekfile-tag
        """
        self.config["pattern_list"] = ["ERROR"]
        log = LogChecker(self.config)

        # create new logfiles
        # Dec  5 12:34:50 hostname test: ERROR
        line1 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line1)

        # Dec  5 12:34:50 hostname test: ERROR
        line2 = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile1, line2)

        # Dec  5 12:34:50 hostname test: ERROR
        line3 = self._make_line(self._get_timestamp(), "noop", "NOOP")
        self._write_logfile(self.logfile2, line3)

        # create seekfile of logfile
        seekfile_1 = LogChecker.get_seekfile(
            self.logfile_pattern, self.SEEKDIR, self.logfile,
            seekfile_tag=self.tag1)
        seekfile_2 = LogChecker.get_seekfile(
            self.logfile_pattern, self.SEEKDIR, self.logfile,
            seekfile_tag=self.tag1)
        seekfile_3 = LogChecker.get_seekfile(
            self.logfile_pattern, self.SEEKDIR, self.logfile,
            seekfile_tag=self.tag2)
        log.check_log(self.logfile, seekfile_3)
        log.clear_state()
        log.check_log_multi(
            self.logfile_pattern, self.SEEKDIR, seekfile_tag=self.tag2)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line2, self.logfile1))
        self.assertEqual(seekfile_1, seekfile_2)
        self.assertNotEqual(seekfile_1, seekfile_3)
        self.assertTrue(seekfile_1.find(self.tag1))
        self.assertTrue(os.path.exists(seekfile_3))

    def test_check(self):
        """LogChecker.check()
        """
        self.config["pattern_list"] = ["ERROR"]
        log = LogChecker(self.config)

        # Dec  5 12:34:50 hostname test: ERROR
        line = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line)

        # check
        log.clear_state()
        log.check(self.logfile, '', self.SEEKDIR)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line, self.logfile))

        # check again
        log.clear_state()
        log.check(self.logfile, '', self.SEEKDIR)

        self.assertEqual(log.get_state(), LogChecker.STATE_OK)

    def test_cache(self):
        """--cache
        """
        self.config["pattern_list"] = ["ERROR"]
        self.config["cache"] = True
        self.config["cachetime"] = 2
        log = LogChecker(self.config)

        # within cachetime
        # Dec  5 12:34:50 hostname test: ERROR
        line = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line)

        # check
        log.clear_state()
        log.check(self.logfile, '', self.SEEKDIR)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line, self.logfile))

        # check again
        log.clear_state()
        log.check(self.logfile, '', self.SEEKDIR)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line, self.logfile))

        os.unlink(self.cachefile)

        # over cachetime
        # Dec  5 12:34:50 hostname test: ERROR
        line = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line)

        log.clear_state()
        log.check(self.logfile, '', self.SEEKDIR)

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line, self.logfile))

        # check again
        time.sleep(self.config["cachetime"] + 1)
        log.clear_state()
        log.check(self.logfile, '', self.SEEKDIR)

        self.assertEqual(log.get_state(), LogChecker.STATE_OK)

        os.unlink(self.cachefile)

    def test_lock_timeout(self):
        """--lock-timeout
        """
        self.config["pattern_list"] = ["ERROR"]
        self.config["lock_timeout"] = 6
        log = LogChecker(self.config)

        # within lock_timeout
        # Dec  5 12:34:50 hostname test: ERROR
        line = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line)

        # locked by an another process
        proc = self._run_locked_subprocess(4)
        time.sleep(2)

        # check
        log.clear_state()
        log.check(self.logfile, '', self.SEEKDIR)
        proc.wait()

        self.assertEqual(log.get_state(), LogChecker.STATE_WARNING)
        self.assertEqual(
            log.get_message(),
            self.MESSAGE_WARNING_ONE.format(line, self.logfile))

        # over lock_timeout
        # Dec  5 12:34:50 hostname test: ERROR
        line = self._make_line(self._get_timestamp(), "test", "ERROR")
        self._write_logfile(self.logfile, line)

        # locked by an another process
        proc = self._run_locked_subprocess(10)
        time.sleep(2)

        # check
        log.clear_state()
        log.check(self.logfile, '', self.SEEKDIR)
        proc.wait()

        self.assertEqual(log.get_state(), LogChecker.STATE_UNKNOWN)
        self.assertEqual(log.get_message(), self.MESSAGE_UNKNOWN_LOCK_TIMEOUT)

    def test_get_prefix_datafile(self):
        """LogChecker.get_prefix_datafile()
        """
        prefix_datafile = LogChecker.get_prefix_datafile(self.seekfile, '', '')
        self.assertEqual(
            prefix_datafile,
            os.path.join(
                os.path.dirname(self.seekfile), LogChecker.PREFIX_DATA))

        prefix_datafile = LogChecker.get_prefix_datafile('', self.SEEKDIR, '')
        self.assertEqual(
            prefix_datafile,
            os.path.join(self.SEEKDIR, LogChecker.PREFIX_DATA))

        prefix_datafile = LogChecker.get_prefix_datafile(
            self.seekfile, self.SEEKDIR, self.tag1)
        self.assertEqual(
            prefix_datafile,
            os.path.join(self.SEEKDIR,
                         "{0}.{1}".format(LogChecker.PREFIX_DATA, self.tag1)))

    def test_lock(self):
        """LogChecker.lock()
        """
        # lock succeeded
        lockfileobj = LogChecker.lock(self.lockfile)
        self.assertNotEqual(lockfileobj, None)
        LogChecker.unlock(self.lockfile, lockfileobj)

        # lock failed
        # locked by an another process
        proc = self._run_locked_subprocess(4)
        time.sleep(2)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lockfileobj = LogChecker.lock(self.lockfile)
        proc.wait()
        self.assertEqual(lockfileobj, None)

    def test_unlock(self):
        """LogChecker.unlock()
        """
        lockfileobj = LogChecker.lock(self.lockfile)
        LogChecker.unlock(self.lockfile, lockfileobj)
        self.assertFalse(os.path.exists(self.lockfile))
        self.assertTrue(lockfileobj.closed)

    def _get_timestamp(self):
        # format: Dec  5 12:34:00
        timestamp = LogChecker.to_unicode(
            datetime.datetime.now().strftime("%b %e %T"))
        return timestamp

    def _get_customized_timestamp(self):
        # format: Thu Dec 05 12:34:56 2013
        timestamp = LogChecker.to_unicode(
            datetime.datetime.now().strftime("%a %b %d %T %Y"))
        return timestamp

    def _make_line(self, timestamp, tag, message):
        # format: Dec  5 12:34:00 hostname noop: NOOP
        line = "{0} hostname {1}: {2}".format(timestamp, tag, message)
        return line

    def _make_customized_line(self, timestamp, level, message):
        # format: [Thu Dec 05 12:34:56 2013] [info] NOOP
        line = "[{0}] [{1}] {2}".format(timestamp, level, message)
        return line

    def _write_logfile(self, logfile, lines, encoding='utf-8'):
        """Write log file for syslog format."""
        fileobj = io.open(logfile, mode='a', encoding=encoding)
        fileobj.write(self._make_line(self._get_timestamp(), "noop", "NOOP"))
        fileobj.write("\n")
        if isinstance(lines, list):
            for line in lines:
                fileobj.write(line)
                fileobj.write("\n")
        else:
            fileobj.write(lines)
            fileobj.write("\n")
        fileobj.write(self._make_line(self._get_timestamp(), "noop", "NOOP"))
        fileobj.write("\n")
        fileobj.flush()
        fileobj.close()

    def _write_customized_logfile(self, logfile, lines, encoding='utf-8'):
        """Write log file for customized format."""
        fileobj = io.open(logfile, mode='a', encoding=encoding)
        fileobj.write(
            self._make_customized_line(
                self._get_customized_timestamp(), "info", "NOOP"))
        fileobj.write("\n")
        if isinstance(lines, list):
            for line in lines:
                fileobj.write(line)
                fileobj.write("\n")
        else:
            fileobj.write(lines)
            fileobj.write("\n")
        fileobj.write(
            self._make_customized_line(
                self._get_customized_timestamp(), "info", "NOOP"))
        fileobj.write("\n")
        fileobj.flush()
        fileobj.close()

    def _run_locked_subprocess(self, sleeptime):
        code = (
            "import time\n"
            "from check_log_ng import LogChecker\n"
            "lockfile = '{0}'\n"
            "lockfileobj = LogChecker.lock(lockfile)\n"
            "time.sleep({1})\n"
            "LogChecker.unlock(lockfile, lockfileobj)\n"
        ).format(self.lockfile, LogChecker.to_unicode(str(sleeptime)))
        code = code.replace("\n", ";")
        proc = subprocess.Popen(['python', '-c', code])
        return proc


if __name__ == "__main__":
    unittest.main()

# vim: set ts=4 sw=4 et:
