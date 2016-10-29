#!/usr/bin/env python

import time
import os
import threading
import sys
from Tkinter import *

# get HZ from /usr/include/asm-generic/param.h
HZ = 100

class killer_ui(object):
    def __init__(self):
        self.cpu_usage_lock = False
        self.cpu_usage = []

        self.root = Tk()
        self.root.title('cpu_monitor')
        #self.root.geometry('500x250')

        # 1. title
        Label(self.root, text = 'proccess cpu_usage > 80%').pack(side = TOP, pady = 10)
    
        # 2. proccess list
        list_frame = Frame(self.root)
        list_frame.pack(side = TOP, pady = 10)
    
        # 2.1 list box
        self.list_var = StringVar()
        # BROWSE | MULTIPLE
        self.list_box = Listbox(list_frame, selectmode = EXTENDED, listvariable = self.list_var)
        self.list_box.pack(side = LEFT)
    
        # 2.2. scroll bar
        scroll_bar = Scrollbar(list_frame)
        scroll_bar.pack(side=RIGHT, fill=Y)
        self.list_box.configure(yscrollcommand = scroll_bar.set)
        scroll_bar['command'] = self.list_box.yview
    
        # 3. count label and select label
        label_frame = Frame(self.root)
        label_frame.pack(side = TOP, pady = 5)
    
        self.count_var  = StringVar()
        self.count_var.set('count: %s' % self.list_box.size())
        self.count_label = Label(label_frame, bg='red', textvariable = self.count_var, width = 20, height = 2)
        self.count_label.pack(side = LEFT)
    
        select_var = StringVar()
        select_var.set('select: 0')
        select_label = Label(label_frame, bg='green', textvariable = select_var, width = 20, height = 2)
        select_label.pack(side = RIGHT)
    
        def update_selections(event):
            select_var.set('select: %s' % len(self.list_box.curselection()))
        self.list_box.bind('<ButtonRelease-1>', update_selections)
        
        # 4. button
        button_frame = Frame(self.root)
        button_frame.pack(side = TOP, pady = 5)
    
        exit_button = Button(button_frame, text = 'exit', command = self.root.quit)
        exit_button.pack(side = LEFT, padx = 20)
    
        kill_all_proc = lambda: self._kill_proc([index for index in range(len(self.cpu_usage))])
        kill_all_button = Button(button_frame, text = 'killall', command = kill_all_proc)
        kill_all_button.pack(side = LEFT, padx = 20)
    
        kill_proc = lambda: self._kill_proc(self.list_box.curselection())
        kill_button = Button(button_frame, text = 'kill', command = kill_proc)
        kill_button.pack(side = RIGHT, padx = 20)
    
    def _kill_proc(self, selections, sig = 9):
        while self.cpu_usage_lock:
            time.sleep(0.5)

        self.cpu_usage_lock = True

        fail_index = []
        for index in selections:
            try:
                os.kill(self.cpu_usage[index][0], sig)
            except OSError, ex:
                # No such process
                if ex.errno != 3:
                    raise Exception('fail to kill pid: %s' % self.cpu_usage[index][0])
            except Exception, ex:
                fail_index.append(index)

        for index in selections:
            if index not in fail_index:
                self.cpu_usage.remove(self.cpu_usage[index])

        self.cpu_usage_lock = False

        self.feed(self.cpu_usage)

    def feed(self, cpu_usage):
        show_info = []
        cnt = 0
        for pid, usage, cmd in cpu_usage:
            cnt += 1
            show_info.append('%4s:%6s:%6s%%:%s' % (cnt, pid, usage, cmd))

        while self.cpu_usage_lock:
            time.sleep(0.5)

        self.cpu_usage_lock = True
        self.list_var.set(show_info[0])
        self.count_var.set(cnt)
        self.cpu_usage = cpu_usage
        self.cpu_usage_lock = False 

    def run(self):
        def deal_feed(event):
            print event
            self.feed([])
        self.root.bind('feed', deal_feed)
        self.root.mainloop()
    
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
    except IOError, ex:
        cmd = '[dead proccess]'

    return cmd

def alert(killer, cpu_usage):
    ''''''
    print cpu_usage
    killer.feed(cpu_usage)
    return

    report_file = '/tmp/cpu_monitor'

    with open(report_file, 'a+') as f:
        for pid, usage, cmd in cpu_usage:
            f.write('%s: %.2f, %s\n' % (pid, usage, cmd))

    #os.system('sudo /sbin/shutdown -k now')

killer = None
def killer_ui_start():
    global killer
    killer = killer_ui()
    killer.run()

def monitor_cpu(limit = 80):
    killer_thread = threading.Thread(target = killer_ui_start)
    killer_thread.start()

    print 'all in'
    delay = 10 # s
    while 1:
        has_alert = False
        try:
            pids = get_running_pid()

            cpu_usage = get_cpu_usage(pids)

            cpu_usage = [(pid, '%.2f' % usage, get_cmd_with_pid(pid))\
                         for pid, usage in cpu_usage if usage > limit]
            if cpu_usage != []:
               global killer
               alert(killer, cpu_usage)
               has_alert = True
        except:
            pass
        finally:
            time.sleep(delay if not has_alert else 1)

    killer_thread.join(0.5)

def main():
    monitor_cpu(limit = 60)
    return
    pid = os.fork()
    if pid == 0:
        monitor_cpu(limit = 60)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
