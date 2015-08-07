#!/usr/bin/env python
# Copyright (C) 2011-2014 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

"""Contains the class OutputStream, a HasTraits file-like text buffer."""

from traits.api import HasTraits, Str, Bool, Trait, Int, List, Font, Float, \
                       Enum, Property
from traitsui.api import View, UItem, TabularEditor
from pyface.api import GUI
from traitsui.tabular_adapter import TabularAdapter
import time

# These levels are identical to sys.log levels
LOG_EMERG      = 0       # system is unusable
LOG_ALERT      = 1       # action must be taken immediately
LOG_CRIT       = 2       # critical conditions
LOG_ERROR      = 3       # error conditions
LOG_WARN       = 4       # warning conditions
LOG_NOTICE     = 5       # normal but significant condition
LOG_INFO       = 6       # informational
LOG_DEBUG      = 7       # debug-level messages

# These log levels are defined uniquely to this module to handle the
# list for stdout, stderror, and the device's log messages
# An unknown log level will end up with - 2
# A python stdout or stderr should come in as - 1

LOG_LEVEL_CONSOLE = -1
LOG_LEVEL_DEFAULT = -2

# This maps the log level numbers to a human readable string
# The unused log levels are commented out of the dict until used

# OTHERLOG_LEVELS will be unmaskable
OTHERLOG_LEVELS  = {
                    LOG_LEVEL_CONSOLE: "CONSOLE",
                    }
# SYSLOG_LEVELS will be maskable

SYSLOG_LEVELS = {#LOG_EMERG : "EMERG",
                 #LOG_ALERT : "ALERT",
                 #LOG_CRIT  : "CRIT",
                 LOG_ERROR : "ERROR",
                 LOG_WARN  : "WARNING",
                 #LOG_NOTICE: "NOTICE",
                 LOG_INFO  : "INFO",
                 LOG_DEBUG : "DEBUG",
                 }

# Combine the log levels into one dict
ALL_LOG_LEVELS = SYSLOG_LEVELS.copy()
ALL_LOG_LEVELS.update(OTHERLOG_LEVELS)

# Set default filter level
DEFAULT_LOG_LEVEL_FILTER = "WARNING"

DEFAULT_MAX_LEN = 250

class LogItemOutputListAdapter(TabularAdapter):
  """
  Tabular adapter for table of log iteritems
  """
  columns = [('Timestamp', 'timestamp'), ('Log level', 'log_level_str'),
             ('Message', 'msg')]
  font = Font('12')
  can_edit = Bool(False)
  timestamp_width = Float(0.18)
  log_level_width = Float(0.07)
  msg_width = Float(0.75)
  can_drop = Bool(False)

class LogItem(HasTraits):
  """
  This class handles items in the list of log entries
  Parameters
  ----------
  log_level  : int
    integer representing the log leve
  timestamp : str
    the time that the console read the log item
  msg : str
    the text of the message
  """
  log_level = Int
  timestamp = Str
  msg = Str

  # log level string maps the int into a the string via the global ALL_LOG_LEVELS dict
  # If we can't find the int in the dict, we print "UNKNOWN"
  log_level_str = Property(fget=lambda self: ALL_LOG_LEVELS.get(self.log_level, "UNKNOWN"),
                   depends_on='log_level')
  def __init__(self, msg, level=None):
    """
    Constructor for logitem
    Notes:
    ----------
    Timestamp initailzies to current system time
    msg is passed in by the user
    If level is passed in as NONE, an attempt is made to infer a log level
    from the msg
    """
    self.log_level = LOG_LEVEL_DEFAULT
    if level == None: # try to infer log level if an old message
      split_colons = msg.split(":")
      # print split_colons[0]
      for key, value in SYSLOG_LEVELS.iteritems():
        # print key
        # print value
        if split_colons[0].lower() == value.lower():
          self.log_level = key
    else:
      self.log_level = level
    # remove line breaks from the message
    self.msg = msg.rstrip('\n')
    # set timestamp
    self.timestamp = time.strftime("%b %d %Y %H:%M:%S")

  def matches_log_level_filter(self, log_level):
    """
    Function to perform filtering of a message based upon the loglevel passed
    Parameters
    ----------
    log_level : int
      Log level on which to filter
    Returns
    ----------
    True if message passes filter
    False otherewise
    """
    if self.log_level <= log_level:
      return True
    else:
      return False


class OutputList(HasTraits):
  """This class has methods to emulate an file-like output list of strings.

  The `max_len` attribute specifies the maximum number of bytes saved by
  the object.  `max_len` may be set to None.

  The `paused` attribute is a bool; when True, text written to the
  OutputList is saved in a separate buffer, and the display (if there is
  one) does not update.  When `paused` returns is set to False, the data is
  copied from the paused buffer to the main text string.
  """

  # Holds LogItems to display
  unfiltered_list = List(LogItem)
  # Holds LogItems while self.paused is True.
  _paused_buffer = List(LogItem)
  # filtered set of messages
  filtered_list = List(LogItem)
  # state of fiter on messages
  log_level_filter = Enum(list(SYSLOG_LEVELS.iterkeys()))
  # The maximum allowed length of self.text (and self._paused_buffer).
  max_len = Trait(DEFAULT_MAX_LEN, None, Int)

  # When True, the 'write' or 'write_level' methods append to self._paused_buffer
  # When the value changes from True to False, self._paused_buffer is copied
  # back to self.unfiltered_list.
  paused = Bool(False)



  def write(self, s):
    """
    Write to the lists OutputList as STDOUt or STDERR.
    This method exist to allow STDERR and STDOUT to be redirected into this
    display. It should only be called when writing to STDOUT and STDERR.
    Ignores spaces.

    Parameters
    ----------
    s : str
      string to cast as LogItem and write to tables
    """

    if not s.isspace():
      log = LogItem(s, LOG_LEVEL_CONSOLE)
      if self.paused:
        self.append_truncate(self._paused_buffer, log)
      else:
        self.append_truncate(self.unfiltered_list, log)
        if log.matches_log_level_filter(self.log_level_filter):
          self.append_truncate(self.filtered_list, log)

  def write_level(self, s, level=None):
    """
    Write to the lists in OutputList from device or user space.

    Parameters
    ----------
    s : str
      string to cast as LogItem and write to tables
    level : int
      Integer log level to use when creating log item.  If this is none, LogItem
      constructer will attempt to infer a log level from the string.
    """
    log = LogItem(s, level)
    if self.paused:
      self.append_truncate(self._paused_buffer, log)
    else:
      self.append_truncate(self.unfiltered_list, log)
      if log.matches_log_level_filter(self.log_level_filter):
        self.append_truncate(self.filtered_list, log)

  def append_truncate(self, buffer, s):
    if len(buffer) > self.max_len:
      assert (len(buffer) - self.max_len) == 1, "Output list buffer is too long"
      buffer.pop()
    buffer.insert(0, s)

  def clear(self):
    self._paused_buffer = []
    self.filtered_list = []
    self.unfiltered_list = []

  def flush(self):
    GUI.process_events()

  def close(self):
    pass

  def _log_level_filter_changed(self):
    self.filtered_list = [item for item in self.unfiltered_list \
                          if item.matches_log_level_filter(self.log_level_filter)]


  def _paused_changed(self):
    """
    Method to call when the paused boolean changes state.
    We need to handle the multiple copies of the buffers.
    """
    if self.paused:
      # Copy the current list to _paused_buffer.  While the OutputStream
      # is paused, the write methods will append its argument to _paused_buffer.
      self._paused_buffer = self.unfiltered_list
    else:
      # No longer paused, so copy the _paused_buffer to the displayed list, and
      # reset _paused_buffer.
      self.unfiltered_list = self._paused_buffer
      # we have to refilter the filtered list too
      self._log_level_filter_changed()
      self._paused_buffer = []

  def traits_view(self):
    view = \
      View(
          UItem('filtered_list',
                editor = TabularEditor(adapter=LogItemOutputListAdapter(), editable=False))
        )
    return view

