import idaapi
import idautils
import idc

# local application/library specific imports
import function
import utils
import hashlib


#==============================================================================
# Client Interface
#==============================================================================
class Actions(object):
    def __init__(self):
        idaapi.show_wait_box("REDB Plugin is loading, please wait...")

        self.functions = {}

        utils._backup_idb_file()
        utils.Configuration.assert_config_file_validity()
        self._collect_string_addresses()
        self.cur_history_item_index = 0
        self.first_undo = 1
        print "*** REDB Plugin loaded. ***"
        idaapi.hide_wait_box()

    def _submit_cur_func(self):
        if not self._set_cur_func():
            return "Not pointing at a function."
        return self.cur_func.submit_description()

    def _request_cur_func(self):
        if not self._set_cur_func():
            return "Not pointing at a function."
        return self.cur_func.request_descriptions()

    def _set_cur_func(self):
        """
        Sets self.cur_func to be the function instance of the function the
        user is currently pointing at. Sets it to None if user is not pointing
        at a function. If current function hasn't been processed using the
        plugin, it is added the function list.
        Returns True iff currently pointing at a function.
        """
        try:
            func = idaapi.get_func(idc.ScreenEA())
        except:
            return False
        if isinstance(func, idaapi.func_t):
            if str(func.startEA) not in self.functions:
                self._add_function(func.startEA)
            self.cur_func = self.functions[str(func.startEA)]
            return True
        else:
            self.cur_func = None
            return False

    def _collect_string_addresses(self):
        self.string_addresses = [string.ea for string in idautils.Strings()]

    def _add_function(self, startEA):
        func = function.Function(startEA, self.string_addresses)
        self.functions[str(startEA)] = func

    def _show_public_description(self, index):
        return self.cur_func.show_description_by_index(index)

    def _show_history_description(self, index):
        return self.cur_func.show_history_item_by_index(index)

    def _undo(self):
        self.cur_history_item_index -= 1
        if self.first_undo == 1:
            self._show_history_description(self.cur_history_item_index)
            self.first_undo = 0
        else:
            selected_description = \
                self.cur_func._history_buffer[self.cur_history_item_index]
            selected_description['desc'].show()

    def _redo(self):
        self.cur_history_item_index += 1
        selected_description = \
             self.cur_func._history_buffer[self.cur_history_item_index]
        selected_description['desc'].show()

    def term(self):
        pass


class HotkeyActions(Actions):
    def __init__(self):
        Actions.__init__(self)
        self._hotkeys = utils._generate_hotkey_table()

    def action(self, arg):
        action_name = self._hotkeys[arg][0]
        if action_name == "Information":
            self._hotkey_information(self._hotkeys)
        elif action_name == "Submit Current":
            self._hotkey_submit_current()
        elif action_name == "Request Current":
            self._hotkey_request_current()
        elif action_name == "Show Public Description":
            self._hotkey_show_public_desc()
        elif action_name == "Show History":
            self._hotkey_show_history_desc()
        elif action_name == "Settings":
            self._hotkey_settings()
        elif action_name == "Undo":
            self._hotkey_undo()
        elif action_name == "Redo":
            self._hotkey_redo()

    def _hotkey_information(self, hotkeys):
        help_string = "\r\nREDB HotkeyActions:\r\n"
        help_string += "===========\r\n"
        for function in hotkeys:
            help_string += function[1]
            help_string += "\t"
            help_string += function[0]
            help_string += "\r\n"
        print help_string

    def _hotkey_submit_current(self):
        print self._submit_cur_func()

    def _hotkey_request_current(self):
        print self._request_cur_func()

    def _get_desc_for_show_index(self, desc_container, prompt_msg):
        num_of_desc = len(desc_container)
        prompt = str(num_of_desc) + prompt_msg

        if num_of_desc == 1:
            defval = "0"
        else:
            defval = "0-" + str((num_of_desc - 1))

        index = idc.AskStr(defval, prompt)
        return int(index)

    def _hotkey_show_public_desc(self):
        if not self._set_cur_func():
            print "Not pointing at a function."
        try:
            index = \
             self._get_desc_for_show_index(self.cur_func._public_descriptions,
                               " public descriptions are available for show")
            self._show_public_description(index)
            self.cur_history_item_index = len(self.cur_func._history_buffer)
            if self.first_undo == 0:
                self.first_undo = 1
                self.cur_func._history_buffer.pop()
        except:
            print "Error: illegal index value"

    def _hotkey_show_history_desc(self):
        if not self._set_cur_func():
            print "Not pointing at a function."
        try:
            index = \
             self._get_desc_for_show_index(self.cur_func._public_descriptions,
                               " history items are available for show")
            self._show_history_description(index)
            self.cur_history_item_index = len(self.cur_func._history_buffer)
            if self.first_undo == 0:
                self.first_undo = 1
                self.cur_func._history_buffer.pop()
        except:
            print "Error: illegal index value"

    def _hotkey_settings(self):
        for opt in utils.Configuration.OPTIONS.keys():
            value = utils.Configuration.get_opt_from_user(opt)
            # User's password isn't saved as-is. It is hashed.
            # The hash is sent to the server, and not the password itself.
            if opt == "password":
                m = hashlib.md5()
                m.update(value)
                value = m.hexdigest()
            utils.Configuration.set_option(opt, value)

    def _hotkey_undo(self):
        if self.cur_history_item_index == 0:
            print "Can't Undo"
        else:
            self._undo()
            print "Undo"

    def _hotkey_redo(self):
        last_history_item_index = len(self.cur_func._history_buffer) - 1
        if self.cur_history_item_index == last_history_item_index:
            print "Can't Redo"
        else:
            self._redo()
            print "Redo"

    def term(self):

        pass


class GuiActions(HotkeyActions):
    def __init__(self, gtk):
        HotkeyActions.__init__(self)
        callbacks = {"on_mainWindow_destroy": self._on_mainWindow_destroy,
                     "on_Submit": self._on_Submit,
                     "on_Request": self._on_Request,
                     "on_Settings": self._on_Settings,
                     "on_Embed": self._on_Embed,
                     "on_Embed_history": self._on_Embed_history,
                     "on_Undo": self._on_Undo,
                     "on_Redo": self._on_Redo,
                     "on_DescriptionTable_cursor_changed":
                        self._on_DescriptionTable_cursor_changed,
                     "on_HistoryTable_cursor_changed":
                        self._on_HistoryTable_cursor_changed}
        self.gui_menu = utils.GuiMenu(callbacks, gtk)

    def action(self, arg):
        action_name = self._hotkeys[arg][0]
        if action_name == "GUI":
            self.load_gui()
        else:
            HotkeyActions.action(self, arg)

    def load_gui(self):
        self.gui_menu.load_xml()
        if self._set_cur_func():
            desc_rows = self._generate_description_rows()
            self.gui_menu.add_descriptions(desc_rows)
            history_rows = self._generate_history_rows()
            self.gui_menu.add_history(history_rows)
        self.gui_menu.show()

    def _on_mainWindow_destroy(self, _):
        self._destroy_main_window()

    def _on_Submit(self, _):
        result = self._submit_cur_func()
        self.gui_menu.set_status_bar(result)

    def _on_Request(self, _):
        result = self._request_cur_func()
        self.gui_menu.set_status_bar(result)

        self.gui_menu.remove_all_rows()
        self.gui_menu.set_details("")
        desc_rows = self._generate_description_rows()
        self.gui_menu.add_descriptions(desc_rows)

    def _on_Settings(self, _):
        HotkeyActions._hotkey_settings(self)
        self.gui_menu.show()
        self.gui_menu.set_status_bar("Settings saved.")

    def _on_Undo(self, _):
        self.cur_history_item_index -= 1
        if self.first_undo == 1:
            self._show_history_description(self.cur_history_item_index)
            self.first_undo = 0
        else:
            selected_description = \
                self.cur_func._history_buffer[self.cur_history_item_index]
            selected_description['desc'].show()
        self.gui_menu.history_buffer.clear()
        history_rows = self._generate_history_rows()
        self.gui_menu.add_history(history_rows)
        self.gui_menu.set_status_bar("Undo")
        if self.cur_history_item_index == 0:
            self.gui_menu.undo_button.set_sensitive(False)  # gray out 'undo' button
        if self.gui_menu.redo_button.get_sensitive() == False:
            self.gui_menu.redo_button.set_sensitive(True)

    def _on_Redo(self, _):
        self.cur_history_item_index += 1
        selected_description = \
             self.cur_func._history_buffer[self.cur_history_item_index]
        selected_description['desc'].show()
        self._handle_history_window()
        self.gui_menu.set_status_bar("Redo")
        last_history_item_index = len(self.cur_func._history_buffer) - 1
        if self.cur_history_item_index == last_history_item_index:
            self.gui_menu.redo_button.set_sensitive(False)  # gray out 'Redo' button
        if self.gui_menu.undo_button.get_sensitive() == False:
            self.gui_menu.undo_button.set_sensitive(True)

    def _on_Embed(self, widget, arg2=None, arg3=None):
        # TODO: check we haven't changed function
        self._handle_undo_redo_buttons()
        index = self.gui_menu.get_selected_description_index()
        result = self._show_public_description(index)
        self._handle_history_window()
        self.cur_history_item_index = len(self.cur_func._history_buffer)
        self.gui_menu.set_status_bar(result)

    def _on_Embed_history(self, widget, arg2=None, arg3=None):
        self._handle_undo_redo_buttons()
        index = self.gui_menu.get_selected_history_index()
        result = self._show_history_description(index)
        self._handle_history_window()
        self.cur_history_item_index = len(self.cur_func._history_buffer)
        self.gui_menu.set_status_bar(result)

    def _on_DescriptionTable_cursor_changed(self, _):
        index = self.gui_menu.get_selected_description_index()
        description = self.cur_func._public_descriptions[index]
        self.gui_menu.set_details(self._data_to_details(description.data))

    def _on_HistoryTable_cursor_changed(self, _):
        index = self.gui_menu.get_selected_history_index()
        description = self.cur_func._history_buffer[index]['desc']
        self.gui_menu.set_details(self._data_to_details(description.data))

    def _handle_undo_redo_buttons(self):
        if self.gui_menu.undo_button.get_sensitive() == False:
            self.gui_menu.undo_button.set_sensitive(True)
        if self.gui_menu.redo_button.get_sensitive() == True:
            self.gui_menu.redo_button.set_sensitive(False)
        if self.first_undo == 0:
            self.first_undo = 1
            self.cur_func._history_buffer.pop()

    def _handle_history_window(self):
        self.gui_menu.history_buffer.clear()
        history_rows = self._generate_history_rows()
        self.gui_menu.add_history(history_rows)

    def _destroy_main_window(self):
        self.gui_menu.hide()

    def _generate_description_rows(self):
        descs = self.cur_func._public_descriptions
        return [[descs.index(desc)] +
                desc.get_public_desc_row() for desc in descs]

    def _generate_history_rows(self):
        history_buffer = self.cur_func._history_buffer
        return [[i] + history_buffer[i]['desc'].get_history_row() + \
                 [history_buffer[i]['prev_desc_details']] for i in
                range(len(history_buffer))]

    def _data_to_details(self, data):
        details = ""

        def list_to_details(lst, line_format):
            details = ""
            for item in lst:
                details += "\t"
                for format_item in line_format:
                    details += format_item + ": "
                    details += str(item[line_format[format_item]]) + "\t\t "
                details += "\n"
            return details

        details += "Function comments:\n"
        func_comments_line_format = {"Repeatable": 0,
                                     "Text": 1}
        details += list_to_details(data["func_comments"],
                                   func_comments_line_format)

        details += "Comments:\n"
        comments_line_format = {"Repeatable": 1,
                                "Relative address": 0,
                                "Text": 2}
        details += list_to_details(data["comments"], comments_line_format)

        details += "Stack members:\n"
        stack_members_line_format = {"Address": 0,
                                     "Name": 1}
        details += list_to_details(data["stack_members"],
                                   stack_members_line_format)
        return details

    def term(self):
        HotkeyActions.term(self)
        self._destroy_main_window()
