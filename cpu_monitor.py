#!/usr/bin/env python

import time
import os
import threading
import sys
import signal
from Tkinter import * 

# get HZ from /usr/include/asm-generic/param.h
HZ = 100

ID_LEN = 4
PID_LEN = 8
CPU_LEN = 8
CMD_LEN = 24

g_stop = False

def prefix_pad(limit, msg):
    msg = '%s' % msg
    if len(msg) >= limit:
        return msg[:limit]
    return (limit - len(msg)) * '. ' + msg

def suffix_pad(limit, msg):
    msg = '%s' % msg
    if len(msg) > limit:
        return msg[:limit]
    return msg + (limit - len(msg)) * '. '

class killer_ui(object):
    __killer__ = None

    @staticmethod
    def get_killer():
        return killer_ui.__killer__

    @staticmethod
    def init_killer(limit):
        killer_ui.__killer__ = killer_ui(limit)
        killer_ui.__killer__.run()

    @staticmethod
    def stop_killer():
        killer_ui.__killer__.root.destroy()
        killer_ui.__killer__ = None

    def __init__(self, limit):
        self.is_select = False
        self.cpu_usage_lock = threading.Lock()
        self.cpu_usage = []
        self.cpu_usage_buffer = []
        self.__killed_pid = []

        self.root = Tk()
        self.root.resizable(False, False)
        self.root.title('cpu_monitor')
        self.root.tk_setPalette(background='black')
        self.root.after(100, self.feed)
        #self.root.geometry('500x250')
        self.root.protocol('WM_DELETE_WINDOW', lambda *ev: self.hide())

        # 1. title
        Label(self.root, text = 'proccess cpu_usage > %s%%' % limit).pack(side = TOP, pady = 10)
    
        # 2. proccess list
        list_frame = Frame(self.root)
        list_frame.pack(side = TOP, expand = True, fill=BOTH)

        # 2.1 list title
        title_info = '%s|%s|%s|%s' % (prefix_pad(ID_LEN, 'ID'), prefix_pad(PID_LEN, 'PID'),
                      prefix_pad(CPU_LEN, '%CPU'), prefix_pad(CMD_LEN, 'CMD  '))
        Label(list_frame, text = title_info, bg = '#3D3D3D', font = ('', 10)).pack(side = TOP)

        # 2.2 list box
        self.list_var = StringVar()
        # BROWSE | MULTIPLE
        self.list_box = Listbox(list_frame, selectmode = EXTENDED, listvariable = self.list_var,
                                width = 32, height = 10, font=('', 10),
                                selectbackground = 'white', selectforeground = 'black')
        self.list_box.pack(side = LEFT, expand = True, fill=BOTH)

        # 2.3. height scroll bar
        y_scroll_bar = Scrollbar(list_frame, orient = VERTICAL)
        y_scroll_bar.pack(side = RIGHT, fill = Y)
        self.list_box.configure(yscrollcommand = y_scroll_bar.set)
        y_scroll_bar['command'] = self.list_box.yview

        def goto_top(event):
            self.list_box.activate(0)
            self.list_box.select_clear(0, END)
            self.list_box.select_set(0)
            self.list_box.yview_moveto(0.0)
        def goto_bottom(event):
            self.list_box.select_clear(0, END)
            self.list_box.activate(END)
            self.list_box.select_set(END)
            self.list_box.yview_moveto(1.0)
        self.list_box.bind('<Double-KeyPress-g>', goto_top)
        self.list_box.bind('<KeyPress-G>', goto_bottom)
    
        # 2.4. width scroll bar
        x_scroll_bar = Scrollbar(self.root, orient = HORIZONTAL)
        x_scroll_bar.pack(side = TOP, fill = X)
        self.list_box.configure(xscrollcommand = x_scroll_bar.set)
        x_scroll_bar['command'] = self.list_box.xview

        def map_h_left(event):
            x_scroll_bar.event_generate('<KeyPress-Left>')
        def map_l_right(event):
            x_scroll_bar.event_generate('<KeyPress-Right>')
        self.list_box.bind('<KeyPress-h>', map_h_left)
        self.list_box.bind('<KeyPress-l>', map_l_right)

        # 3. count label and select label
        label_frame = Frame(self.root)
        label_frame.pack(side = TOP, pady = 5)
    
        self.count_var  = StringVar()
        self.count_var.set('count: %s' % self.list_box.size())
        self.count_label = Label(label_frame, bg = 'red', textvariable = self.count_var, width = 20, height = 2)
        self.count_label.pack(side = LEFT)
    
        self.select_var = StringVar()
        self.select_var.set('select_cnt: 0')
        select_label = Label(label_frame, bg='green', textvariable = self.select_var, width = 20, height = 2)
        select_label.pack(side = RIGHT)
    
        def update_selections(event):
            self.cpu_usage_lock.acquire()
            cnt = len(self.list_box.curselection())
            self.select_var.set('select_cnt: %s' % cnt)
            self.is_select = (cnt > 0)
            self.cpu_usage_lock.release()
        self.list_box.bind('<ButtonRelease-1>', update_selections)
        self.list_box.bind('<KeyRelease-Up>', update_selections)
        self.list_box.bind('<KeyRelease-Down>', update_selections)

        def map_j_Down(event):
            self.list_box.event_generate('<KeyPress-Down>')
            update_selections(event)
        def map_shift_j_Down(event):
            self.list_box.event_generate('<Shift-KeyPress-Down>')
            update_selections(event)
        def map_k_Up(event):
            self.list_box.event_generate('<KeyPress-Up>')
            update_selections(event)
        def map_shift_k_Up(event):
            self.list_box.event_generate('<Shift-KeyPress-Up>')
            update_selections(event)
        self.list_box.bind('<KeyPress-j>', map_j_Down)
        self.list_box.bind('<KeyPress-J>', map_shift_j_Down)
        self.list_box.bind('<KeyPress-k>', map_k_Up)
        self.list_box.bind('<KeyPress-K>', map_shift_k_Up)

        def clear_selections(event):
            self.cpu_usage_lock.acquire()
            self.list_box.select_clear(0, self.list_box.size())
            self.select_var.set('select_cnt: 0')
            self.is_select = False
            self.cpu_usage_lock.release()
        self.list_box.bind('<ButtonRelease-3>', clear_selections)
        self.list_box.bind('<Double-1>', clear_selections)
        self.list_box.bind('<Escape>', clear_selections)
        
        # 4. button
        button_frame = Frame(self.root)
        button_frame.pack(side = TOP, pady = 5)
    
        exit_button = Button(button_frame, text = 'exit', command = self.hide)
        exit_button.pack(side = LEFT, padx = 20)
        exit_button.bind('<Return>', lambda event: self.hide())
    
        killall_button = Button(button_frame, text = 'killall',
                command = lambda: self.kill_proc(range(len(self.cpu_usage))))
        killall_button.pack(side = LEFT, padx = 20)
        killall_button.bind('<Return>', lambda event: self.kill_proc(range(len(self.cpu_usage))))
    
        kill_button = Button(button_frame, text = 'kill',
                command = lambda: self.kill_proc(self.list_box.curselection()))
        kill_button.pack(side = RIGHT, padx = 20)
        kill_button.bind('<Return>', lambda event: self.kill_proc(self.list_box.curselection()))

        # 5. bind short-key
        self.root.bind('<Control-KeyPress-x>',
                       lambda event: self.kill_proc(self.list_box.curselection()))
        self.root.bind('<Control-KeyPress-X>',
                       lambda event: self.kill_proc(range(len(self.cpu_usage))))
        self.root.bind('<Control-KeyPress-h>',
                       lambda event: self.hide())

    def hide(self):
        self.root.withdraw()

    def show(self):
        self.root.update()
        self.root.deiconify()

    def gen_show_info(self, cpu_usage = None):
        if cpu_usage == None:
            cpu_usage = self.cpu_usage

        cnt = 0
        show_info = ()
        for pid, usage, cmd in cpu_usage:
            cnt += 1
            show_info += ('%s|%s|%s|%s' % (prefix_pad(ID_LEN, cnt), prefix_pad(PID_LEN, pid),
                          prefix_pad(CPU_LEN, '%s%%' % usage), cmd),)

        return show_info

    def kill_proc(self, selections, sig = 9):
        if len(selections) == 0:
            return

        self.cpu_usage_lock.acquire()

        fail_index = []
        for index in selections:
            try:
                os.kill(self.cpu_usage[index][0], sig)
            except OSError, ex:
                # No such process
                if ex.errno != 3:
                    raise ex
            except Exception, ex:
                fail_index.append(index)

        cpu_usage_cp = self.cpu_usage[:]
        for index in selections:
            if index not in fail_index:
                self.__killed_pid.append(cpu_usage_cp[index][0])
                self.cpu_usage.remove(cpu_usage_cp[index])
                for proc in self.cpu_usage_buffer:
                    if proc[0] == cpu_usage_cp[index][0]:
                        self.cpu_usage_buffer.remove(proc)

        self.list_var.set(self.gen_show_info(self.cpu_usage))
        self.count_var.set('count: %s' % len(self.cpu_usage))

        self.is_select = False
        self.select_var.set('select_count: 0')
        self.cpu_usage_lock.release()

    def feed(self):
        if g_stop:
            killer_ui.stop_killer()
            return

        self.cpu_usage_lock.acquire()
        if self.is_select:
            self.cpu_usage_lock.release()
            self.root.after(1000, self.feed)
            return

        if len(self.cpu_usage_buffer) > 0:
            self.cpu_usage = self.cpu_usage_buffer
            show_info = self.gen_show_info(self.cpu_usage)
            self.list_var.set(show_info)
            self.count_var.set('count: %s' % len(self.cpu_usage))
            self.cpu_usage_buffer = []

        self.cpu_usage_lock.release()
        self.root.after(500, self.feed)

    def run(self):
        self.hide()
        self.root.mainloop()

    def async_feed(self, cpu_usage):
        while not self.cpu_usage_lock.acquire(True):
            if g_stop:
                return
            time.sleep(0.1)

        # clear
        self.cpu_usage_buffer = []

        for proc in cpu_usage:
            if proc[0] not in self.__killed_pid:
                self.cpu_usage_buffer.append(proc)

        # clear
        self.__killed_pid = []

        self.cpu_usage_lock.release()

        self.show()

def get_running_pid():
    ''''''

    def is_digit(digit_str, base = 10):
        try:
            _ = long(digit_str, base)
            return True
        except:
            return False

    names = os.listdir('/proc/')

    pids = []
    for name in names:
        if os.path.isdir(os.path.join('/proc/', name)) and is_digit(name):
            pids.append(name)

    return pids

def get_cpu_use(pid = -1):
    ''''''

    if pid == -1:
        stat_file = '/proc/self/stat'
    else:
        stat_file = '/proc/%s/stat' % pid

    try:
        with open(stat_file, 'r') as f:
            buff = f.readline()
            items = buff.split(' ')
            cpu_use = int(items[13]) + int(items[14])
    except IOError, ex:
        # proccess has already exited
        cpu_use = None

    return cpu_use

class cpu_use_info(object):
    def __init__(self, pid = -1, use = 0.0, timestamp = 0.0):
        self.pid = pid
        self.use = use
        self.timestamp = timestamp

    def __repr__(self):
        return '%s:%s:%.3f' % (self.pid, self.use, self.timestamp)

def get_cpu_use_multi(pids = []):
    ''''''

    cpu_use = {}
    for pid in pids:
        use = get_cpu_use(pid)
        if use != None:
            cpu_use[pid] = cpu_use_info(pid, use, time.time())

    return cpu_use

def map_intersect(map1, map2):
    common_keys = set(map1.keys())
    common_keys.intersection_update(map2.keys())
    return common_keys

def map_item_sub(map1, map2):
    common_keys = map_intersect(map1, map2)
    res_map = {}
    for key in common_keys:
        usage = (map1[key].use - map2[key].use)\
                / ((map1[key].timestamp - map2[key].timestamp) * HZ)
        res_map[key] = cpu_use_info(key, usage)

    return res_map

def map_item_add(map1, map2):
    if len(map1) == 0:
        return map2
    if len(map2) == 0:
        return map1

    common_keys = map_intersect(map1, map2)

    res_map = {}
    for key in common_keys:
        res_map[key] = cpu_use_info(pid = key, use = map1[key].use + map2[key].use)

    return res_map

def get_cpu_usage(pids = []):
    ''''''
    delt = 0.1

    cnt = 5
    cpu_use = []

    for _ in range(cnt):
        cpu_use.append(get_cpu_use_multi(pids))
        time.sleep(delt)

    cpu_usage = {}
    for i in range(cnt - 1):
        use = map_item_sub(cpu_use[i + 1], cpu_use[i])
        cpu_usage = map_item_add(cpu_usage, use)

    usage_list = []
    for key in cpu_usage.keys():
        cpu_usage[key] = cpu_usage[key].use / (cnt - 1) * 100
        usage_list.append((key, cpu_usage[key]))

    def _cmp(x, y):
        if x[1] > y[1]: return -1
        if x[1] < y[1]: return 1
        return 0

    usage_list.sort(cmp = _cmp)

    return usage_list

def get_cmd_with_pid(pid):
    ''''''

    cmd_file = '/proc/%s/cmdline' % pid

    try:
        with open(cmd_file, 'r') as f:
            cmd = f.read()
        if cmd.endswith('\x00'):
            cmd = cmd[:-1]
    except IOError, ex:
        cmd = '[dead proccess]'

    return cmd

def alert(cpu_usage):
    ''''''

    killer = killer_ui.get_killer()
    if killer:
        killer.async_feed(cpu_usage)
    else:
        report_file = '/tmp/cpu_monitor'

        with open(report_file, 'a+') as f:
            for pid, usage, cmd in cpu_usage:
                f.write('%s: %s, %s\n' % (pid, usage, cmd))

        os.system('sudo /sbin/shutdown -k now')

def sig_handler(sig, stack):
    global g_stop
    g_stop = True

def monitor_cpu(limit = 80):
    killer_thread = threading.Thread(target = killer_ui.init_killer,
                                     args = (limit,))
    killer_thread.start()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    delay = 10 # s
    while not g_stop:
        has_alert = False
        pids = get_running_pid()

        cpu_usage = get_cpu_usage(pids)

        cpu_usage = [(int(pid), '%.2f' % usage, get_cmd_with_pid(pid))\
                     for pid, usage in cpu_usage if usage > limit]
        if cpu_usage != []:
            alert(cpu_usage)
            has_alert = True
        time.sleep(delay if not has_alert else 1)

    killer_thread.join()

def main():
    pid = os.fork()
    if pid == 0:
        monitor_cpu(limit = 60)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
