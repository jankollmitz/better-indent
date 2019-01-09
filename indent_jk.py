import sublime
import sublime_plugin
import string
import time
import re

# The pre-compiled regex pattern to parse indenation scopes. Group 1 is '.next'
# or none to determine the line where the indentaion should be applied, group 2
# is the indentaion level difference.
pattern = re.compile(r'indentation(\.next)?\.((\+|\-)[1-9])')

def check_for_indent_inc(view, pt):
  return view.match_selector(pt, 'indentation.inc')

def check_for_indent_dec(view, pt):
  return view.match_selector(pt, 'indentation.dec')

def check_for_indent_inc_next(view, pt):
  return view.match_selector(pt, 'indentation.next.inc')

def check_for_indent_dec_next(view, pt):
  return view.match_selector(pt, 'indentation.next.dec')


def calc_indent_level(view, line, prev_line):
  inc = 0
  dec = 0
  # check for indentation scopes in this line
  for pt in range(line.begin(), line.end() + 1):
    inc = max(inc, check_for_indent_inc(view, pt))
    dec = max(dec, check_for_indent_dec(view, pt))

  # check for indentation.next scopes in the previous line
  for pt in range(prev_line.begin(), prev_line.end() + 1):
    inc = max(inc, check_for_indent_inc_next(view, pt))
    dec = max(dec, check_for_indent_dec_next(view, pt))

  # get current indent level from previous line
  # prev_level = view.indentation_level(prev_line.a)

  return (inc - dec)

def set_indent_level(view, edit, line, level):
  # Check if the line needs editing
  # print( view.indentation_level(line.begin()), level)
  if view.indentation_level(line.begin()) == level:
    return
  content = view.substr(line).lstrip()
  indented_content = '\t' * max(0, level) + content
  # print(content)
  # print(indented_content)
  view.replace(edit, line, indented_content)

# Get previous non-empty line
def get_previous_line(view, line):
  prev_line = view.line(line.a - 1)
  # Iterate through previous lines until a non-empty line.
  while view.substr(line).lstrip() == "":
    prev_line = view.line(prev_line.a - 1)
  return prev_line

def indent_current_line(view, edit):
  cursor = view.sel()[0].begin()
  # print(view.match_selector(cursor, 'indentation.next.inc'))
  # print(view.score_selector(cursor, 'indentation.next.inc'))
  # print(view.score_selector(cursor, 'indentation.next.inc.1'))
  # print(view.score_selector(cursor, 'indentation.next.inc.2'))
  # print(view.scope_name(cursor))
  # return
  line = view.line(cursor)
  # print(cursor, line)
  # get previous line
  prev_line = view.line(view.text_point(view.rowcol(line.begin())[0]-1, 0))
  # print(prev_line)
  if line == prev_line:
    set_indent_level(view, edit, line, 0)
    return

  # TODO check if last line is empty
  current_level = view.indentation_level(prev_line.begin())
  level_diff = calc_indent_level(view, line, prev_line)
  set_indent_level(view, edit, line, current_level + level_diff)

def reindent_all_lines(view, edit):
  t1 = time.perf_counter()
  # check only for indentation selector and parse the rest
  diff = [0 for i in range(view.rowcol(view.size())[0])]
  for region in view.find_by_selector('indentation'):
    scope =  view.scope_name(region.a)
    match = pattern.search(scope)
    # if not match:
    #   # Should always match unless there is some error in the syntax definition.
    #   # TODO(Jan) error
    #   return -1
    while match:
      # Parse the indentation information from matched groups 1 and 2.
      if match.group(1) == '.next':
        row = view.rowcol(region.a)[0] + 1
      else:
        row = view.rowcol(region.a)[0]
      # check if not in the last line
      if row < len(diff):
        diff[row] = diff[row] + int(match.group(2))
      # Look for other matches in the rest of the scope
      scope = scope[match.span(0)[1]:]
      match = pattern.search(scope)

  t2 = time.perf_counter()

  # maybe improve this
  level = 0
  for i in range(len(diff)):
    level = level + diff[i]
    line = view.line(view.text_point(i, 0))
    if view.substr(line).lstrip() != '':
      set_indent_level(view, edit, line, level)

  t3 = time.perf_counter()
  print("reindent_all_lines_3 calc:", t2 - t1, ", indent:", t3-t2)

class BetterReindentCommand(sublime_plugin.TextCommand):
  def run(self, edit, selection=False):
    view = self.view
    reindent_all_lines(view, edit)
    # # Get all lines to be indented as a list of regions.
    # if selection:
    #   sel = view.sel()
    #   lines = []
    #   for i in range(len(sel)):
    #     lines = lines + view.lines(sel[i])
    # else:
    #   lines = view.lines(sublime.Region(0, view.size()))

    # print(lines)
    # # Check if lines contains first line and if so, indent to 0 and remove from
    # # lines.
    # if lines[0].a == 0:
    #   set_indent_level(view, edit, lines[0], 0)
    #   lines = lines[1:]

    # # Forward loop to compute indentation level.
    # level = [0 for i in range(len(lines))]
    # for i, line in enumerate(lines):
    #   line = lines[i]
    #   prev_line = get_previous_line(view, line)
    #   # print(line, prev_line)
    #   level[i] = calc_indent_level(view, line, prev_line)
    # print(level)
    # # Backwards loop to set indentation level --> doesn't mess with numbers of
    # # line beginning.
    # for i, line in reversed(list(enumerate(lines))):
    #   set_indent_level(view, edit, line, level[i])


class BetterAutoIndent(sublime_plugin.ViewEventListener):
  def __init__(self, view):
    super(BetterAutoIndent, self).__init__(view)
    # self.running = 0
    self.last_count = self.view.change_count()
    self.last_line_pos = 0
    self.last_line = ""

  def is_applicable(settings):
    return settings.get('better_auto_indent', False)

  def on_selection_modified(self):
    print(self.view.command_history(0))
    # line_pos = self.view.sel()[0].begin()
    # if self.last_count == self.view.change_count():
    #   last_line = line
    #   return

    # if line != last_line:
    #   # Something changed and we're in a new line
    #   self.view.run_command('better_reindent')
    #   return



    # line = self.view.substr(self.view.line(self.view.sel()[0].begin())).strip()

    # if self.last_count != self.view.change_count():
    #   if line != self.last_line:
    #     self.last_line = line
    #     self.view.run_command('better_reindent')
    # self.last_count = self.view.change_count()
    # self.last_line = line
