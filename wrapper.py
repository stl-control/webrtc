import os
import re
import json
import webview
import subprocess
from screeninfo import get_monitors
from scapy.all import dev_from_networkname, get_working_ifaces, sendp, Ether, ARP

title = "Video Conference"
url = "https://2ly.link/24LJH"


if os.name == 'nt':
  import ctypes
  user32 = ctypes.windll.user32
  user32.SetProcessDPIAware()

screen = None
interface_name = os.environ['INTERFACE'] if 'INTERFACE' in os.environ and os.environ['INTERFACE'] else ''
interface = dev_from_networkname(interface_name) if interface_name else None
channel_id = int(os.environ['CHANNEL_ID']) if 'CHANNEL_ID' in os.environ and os.environ['CHANNEL_ID'] else 1
event_id = 0

print('Available screens are: ' + str(webview.screens))

def signed_int_to_byte(val):
  return 256 + val if val < 0 else val

def relay_event(event):
  global event_id
  data = []
  if event['type'] == "key":
    data = [1, 1 if event['state'] else 0]
    data.extend([ord(c) for c in event['key']])
    if event['finish']:
      data[1] |= 0x02
  elif event['type'] == "mouse_button":
    data = [2, 1 if event['state'] else 0]
    data.extend([ord(c) for c in event['button']])
  elif event['type'] == "mouse_move":
    data = [
      3,
      (event['to']['x'] >> 8) & 0xFF, event['to']['x'] & 0xFF,
      (event['to']['y'] >> 8) & 0xFF, event['to']['y'] & 0xFF,
    ]
  elif event['type'] == "mouse_wheel":
    data = [5, 0, #(event.squash ? 1 : 0),
            signed_int_to_byte(event['delta']['x']),
            signed_int_to_byte(event['delta']['y'])]
  if data:
    # print(data)
    ether = Ether(dst="ff:ff:ff:ff:ff:ff")
    arp = ARP(op=1, hwsrc=ether.src, psrc="0.0.0.0", hwdst="00:00:00:00:00:00", pdst="0.0.0.0")
    event_id_buf = bytes([event_id])
    extra_data = bytes([channel_id % 256]) + event_id_buf + bytes(data)
    packet = ether / arp / extra_data
    event_id = (event_id + 1) % 256
    sendp(packet, iface=interface, verbose=0)

class JsApi:
  def get_channel_id(self):
    return channel_id
  
  def get_screens(self):
    data = {}
    index = 0
    monitors = get_monitors()
    names = [m.name for m in monitors]
    if os.name == 'nt':
      proc = subprocess.Popen(['powershell', 'Get-WmiObject win32_desktopmonitor;'], stdout=subprocess.PIPE)
      res = proc.communicate()
      names = re.findall('(?s)\r\nName\s+:\s(.*?)\r\n', res[0].decode("utf-8"))
    for m in monitors:
      name = names[index] if index < len(names) else f"Display {index+1}"
      index += 1
      data[index] = f"{name} ({m.width}x{m.height} at {m.x},{m.y})"
    return data
  
  def get_interfaces(self):
    interfaces = {}
    for iface in get_working_ifaces():
      if iface.is_valid():
        if not iface.ip:
          continue
        if iface.ip.startswith('169.254.') or iface.ip.startswith('127.0.'):
          continue
        interfaces[iface.network_name] = f"{iface.name} {iface.description} ({iface.ip})"
    return interfaces
  
  def handle_message(self, data):
    try:
      event = json.loads(data)
      relay_event(event)
    except:
      pass

  def handle_camera_select(self, device_id):
    return

  def handle_channel_select(self, value):
    global channel_id
    channel_id = int(value)
  
  def handle_interface_select(self, iface):
    global interface_name, interface
    interface_name = iface
    interface = dev_from_networkname(iface)
  
  def handle_screen_select(self, index):
    global screen
    try:
      screen = webview.screens[int(index)-1]
    except:
      screen = None
  
  def handle_open_room(self, roomid, pref):
    global window
    domain = window.evaluate_js('window.location.origin')
    codecs = pref['codecs'] if 'codecs' in pref else 'h264'
    url = domain + f"/host.html?open=true&userid={roomid}-portal&roomid={roomid}&codecs={codecs}"
    if window.dom.get_element('#password'):
      password = window.dom.get_element('#password').value
      if password:
        url += f"&password={password}"
    fullscreen = window.evaluate_js('document.getElementById("fullscreen").checked')
    if fullscreen:
      url += "&fullscreen=true"
    _w = webview.create_window(title, url,
                            js_api=JsApi(),
                            screen=screen,
                            fullscreen=fullscreen,
                            on_top=fullscreen,
                            width=1200, height=800)
    window.destroy()
    window = _w

  def toggle_fullscreen(self):
    window.toggle_fullscreen()
    window.on_top = not window.on_top

def handler(window):
  el = window.dom.get_element('#channel-id')
  if el:
    el.value = str(channel_id)
  
  el = window.dom.get_element('#select-interface')
  if el and interface_name:
    el.value = interface_name


webview.settings = {
  "OPEN_EXTERNAL_LINKS_IN_BROWSER": False,
}
window = webview.create_window(title, url, js_api=JsApi(),
                               width=1200, height=800)
script_path = os.path.abspath(os.path.dirname(__file__))
data_path = os.path.join(script_path, "pywebview")
webview.start(handler, window,
              private_mode=False, storage_path=data_path)