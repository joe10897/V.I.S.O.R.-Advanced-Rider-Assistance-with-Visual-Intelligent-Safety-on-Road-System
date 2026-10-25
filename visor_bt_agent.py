#!/usr/bin/env python3
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import os

# 設定藍牙 Agent 介面
BUS_NAME = 'org.bluez'
AGENT_INTERFACE = 'org.bluez.Agent1'
AGENT_PATH = "/test/agent"

class Agent(dbus.service.Object):
    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        print(f"[V.I.S.O.R.] 授權服務: {uuid} 來自 {device}")
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        print(f"[V.I.S.O.R.] 請求 PIN 碼: {device}")
        return "0000"

    @dbus.service.method(AGENT_INTERFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        print(f"[V.I.S.O.R.] 自動確認配對: {device} (Passkey: {passkey})")
        # 將裝置設為 Trusted (信任)，下次連線無需再次配對
        try:
            obj = dbus.Interface(bus.get_object(BUS_NAME, device), "org.freedesktop.DBus.Properties")
            obj.Set("org.bluez.Device1", "Trusted", True)
        except Exception as e:
            print(f"Error setting trust: {e}")
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        print(f"[V.I.S.O.R.] 顯示配對碼: {passkey} 來自: {device}")
        try:
            obj = dbus.Interface(bus.get_object(BUS_NAME, device), "org.freedesktop.DBus.Properties")
            obj.Set("org.bluez.Device1", "Trusted", True)
        except Exception:
            pass

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        print(f"[V.I.S.O.R.] 請求 Passkey: {device}")
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        print(f"[V.I.S.O.R.] 授權配對: {device}")
        try:
            obj = dbus.Interface(bus.get_object(BUS_NAME, device), "org.freedesktop.DBus.Properties")
            obj.Set("org.bluez.Device1", "Trusted", True)
        except Exception:
            pass
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Cancel(self):
        print("[V.I.S.O.R.] 配對取消")

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    # 確保藍牙處於可發現與配對狀態
    os.system("bluetoothctl discoverable on")
    os.system("bluetoothctl pairable on")

    agent = Agent(bus, AGENT_PATH)
    obj = bus.get_object(BUS_NAME, "/org/bluez")
    manager = dbus.Interface(obj, "org.bluez.AgentManager1")
    manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
    manager.RequestDefaultAgent(AGENT_PATH)

    print("[V.I.S.O.R.] 藍牙自動配對代理人已啟動...")
    print("[V.I.S.O.R.] Pi 5 現在處於可發現狀態，請開啟手機藍牙搜尋。")

    mainloop = GLib.MainLoop()
    mainloop.run()
