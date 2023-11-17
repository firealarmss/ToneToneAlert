# Caleb, KO4UYJ
#
# Tone detection software geared towards fire department style alerting
#
# Portions of this software Copyright https://github.com/syastrov/twotonedecoder

NUM_TONES = 2
MIN_TONE_FREQUENCY_DIFFERENCE = 10.0
MIN_TONE_LENGTH = 1.000
MAX_TONE_FREQ_STD_DEVIATION = 15.0
SQUELCH = -70.

import sys
import threading
import queue
import asyncio

import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter.font import Font

from socketlabs.injectionapi import SocketLabsClient
from socketlabs.injectionapi.message.basicmessage import BasicMessage
from socketlabs.injectionapi.message.emailaddress import EmailAddress
from twilio.rest import Client
import requests
import wave
import time
from datetime import datetime
import pyaudio
from pydub import AudioSegment
from pydub.playback import play
from pydub import AudioSegment
import os
import base64
import yaml
import serial
import numpy
from playsound import playsound
from kasa import SmartPlug, SmartBulb, SmartLightStrip

with open('db.yml', 'r') as file:
    departments = yaml.load(file, Loader=yaml.FullLoader)

with open('config.yml', 'r') as file:
    config = yaml.load(file, Loader=yaml.FullLoader)

if (config["socketLabs"]["enable"]):
    client = SocketLabsClient(config["socketLabs"]["serverId"], config["socketLabs"]["clientId"])

account_sid = config["twilio"]["accountSid"]
auth_token = config["twilio"]["authToken"]

COMMANDS = {
    "status": {
        1: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x01, 0x00]),
        2: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x02, 0x00]),
        3: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x03, 0x00]),
        4: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x04, 0x00]),
    },
    "on": {
        1: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x01, 0x01]),
        2: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x02, 0x01]),
        3: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x03, 0x01]),
        4: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x04, 0x01]),

    },
    "off": {
        1: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x01, 0x02]),
        2: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x02, 0x02]),
        3: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x03, 0x02]),
        4: bytearray([0x55, 0x56, 0x00, 0x00, 0x00, 0x04, 0x02]),
    },
}

RESPONSES = {
    "on": {
        1: bytearray([0x33, 0x3C, 0x00, 0x00, 0x00, 0x01, 0x01, 0x71]),
        2: bytearray([0x33, 0x3C, 0x00, 0x00, 0x00, 0x02, 0x01, 0x72]),
        3: bytearray([0x33, 0x3C, 0x00, 0x00, 0x00, 0x03, 0x01, 0x73]),
        4: bytearray([0x33, 0x3C, 0x00, 0x00, 0x00, 0x04, 0x01, 0x74]),
    },
    "off": {
        1: bytearray([0x33, 0x3C, 0x00, 0x00, 0x00, 0x01, 0x02, 0x72]),
        2: bytearray([0x33, 0x3C, 0x00, 0x00, 0x00, 0x02, 0x02, 0x73]),
        3: bytearray([0x33, 0x3C, 0x00, 0x00, 0x00, 0x03, 0x02, 0x74]),
        4: bytearray([0x33, 0x3C, 0x00, 0x00, 0x00, 0x04, 0x02, 0x75]),
    }
}

chunk = 2048

p = pyaudio.PyAudio()

stream = p.open(format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                input=True,
                # output=True,
                frames_per_buffer=chunk)


#
# requests.post('https://api.mynotifier.app', {
#     "apiKey": 'd2953cdb-7737-40da-b502-bbc689594bcf',
#     "message": "Our first notification!",
#     "description": "This is cool",
#     "type": "warning", # info, error, warning or success
# })

def on_button_click():
    pass


def setup_gui(root):
    global activeAlert, tone1_box, tone2_box, user_management_frame, alert_frame, tone_frame

    custom_font = Font(family="Helvetica", size=20)

    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TEntry', foreground='#333', font=custom_font)
    style.configure('TButton', font=custom_font, background='#5DADE2', foreground='#FFF')

    notebook = ttk.Notebook(root)
    notebook.pack(expand=True, fill='both')

    tone_frame = ttk.Frame(notebook, padding="10")
    alert_frame = ttk.Frame(notebook, padding="10")

    notebook.add(tone_frame, text='Tones')
    notebook.add(alert_frame, text='Alerts')

    user_management_frame = ttk.Frame(notebook, padding="10")
    notebook.add(user_management_frame, text='Manage Users')

    audio_settings_frame = ttk.Frame(notebook, padding="10")
    notebook.add(audio_settings_frame, text='Audio Settings')

    setup_user_management_tab(user_management_frame, root)

    setup_audio_settings_tab(audio_settings_frame)

    ttk.Label(tone_frame, text="Tone 1:", font=custom_font).grid(row=0, column=0, padx=5)
    tone1_box = ttk.Entry(tone_frame, style='TEntry', width=15)
    tone1_box.grid(row=0, column=1, padx=5)
    #  tone1_box.state([tk.DISABLED])

    ttk.Label(tone_frame, text="Tone 2:", font=custom_font).grid(row=1, column=0, padx=5)
    tone2_box = ttk.Entry(tone_frame, style='TEntry', width=15)
    tone2_box.grid(row=1, column=1, padx=5)
    #    tone2_box.state([tk.DISABLED])

    ttk.Label(alert_frame, text="Active Alert:", font=custom_font).grid(row=0, column=0, padx=5)
    activeAlert = tk.Text(alert_frame, height=15, width=50, font=custom_font)
    activeAlert.grid(row=1, column=0, padx=5)

    tone_gen_frame = ttk.Frame(notebook, padding="10")
    notebook.add(tone_gen_frame, text='Generate Tones')
    setup_tone_generation_tab(tone_gen_frame)


def setup_audio_settings_tab(frame):
    global selected_mic_var, selected_speaker_var
    selected_mic_var = tk.StringVar()
    selected_speaker_var = tk.StringVar()

    ttk.Label(frame, text="Microphone Settings").grid(row=0, column=0, padx=5, pady=5)
    ttk.Label(frame, text="Speaker Settings").grid(row=0, column=1, padx=5, pady=5)

    mic_menu = ttk.Combobox(frame, textvariable=selected_mic_var)
    mic_menu.grid(row=1, column=0, padx=5, pady=5)

    speaker_menu = ttk.Combobox(frame, textvariable=selected_speaker_var)
    speaker_menu.grid(row=1, column=1, padx=5, pady=5)

    pa = pyaudio.PyAudio()
    mic_devices = []
    speaker_devices = []
    for i in range(pa.get_device_count()):
        device_info = pa.get_device_info_by_index(i)
        if device_info['maxInputChannels'] > 0:
            mic_devices.append(device_info.get('name'))
        if device_info['maxOutputChannels'] > 0:
            speaker_devices.append(device_info.get('name'))

    mic_menu['values'] = mic_devices
    speaker_menu['values'] = speaker_devices

    if mic_devices:
        selected_mic_var.set(mic_devices[0])
    if speaker_devices:
        selected_speaker_var.set(speaker_devices[0])

    save_button = ttk.Button(frame, text="Save Settings", command=save_audio_settings)
    save_button.grid(row=2, column=0, columnspan=2, padx=5, pady=5)


def save_audio_settings():
    selected_mic = selected_mic_var.get()
    selected_speaker = selected_speaker_var.get()
    print(f"Selected Microphone: {selected_mic}")
    print(f"Selected Speaker: {selected_speaker}")


def setup_tone_generation_tab(frame):
    global tone_a_combobox, tone_b_combobox

    tone_frequencies = [
        330.5, 349.0, 368.5, 389.0, 410.8, 433.7, 457.9, 483.5, 510.5, 539.0,  # Group 1
        569.1, 600.9, 634.5, 669.9, 707.3, 746.8, 788.5, 832.5, 879.0, 928.1,  # Group 2
        288.5, 296.5, 304.7, 313.8, 953.7, 979.9, 1006.9, 1034.7, 1063.2, 1092.4,  # Group 3
        321.7, 339.6, 358.6, 378.6, 399.8, 422.1, 445.7, 470.5, 496.8, 524.6,  # Group 4
        553.9, 584.8, 617.4, 651.9, 688.3, 726.8, 767.4, 810.2, 855.5, 903.2,  # Group 5
        1122.5, 1153.4, 1185.2, 1217.8, 1251.4, 1285.8, 1321.2, 1357.6, 1395.0, 1433.4,  # Group 6
        1472.9, 1513.5, 1555.2, 1598.0, 1642.0, 1687.2, 1733.7, 1781.5, 1830.5, 1881.0,  # Group 10
        1930.2, 1989.0, 2043.8, 2094.5, 2155.6, 2212.2, 2271.7, 2334.6, 2401.0, 2468.2,  # Group 11
    ]

    tone_a_label = ttk.Label(frame, text="Tone A Frequency (Hz):")
    tone_a_label.grid(row=0, column=0, padx=5, pady=5)
    tone_a_combobox = ttk.Combobox(frame, values=tone_frequencies, state="readonly")
    tone_a_combobox.grid(row=0, column=1, padx=5, pady=5)

    tone_b_label = ttk.Label(frame, text="Tone B Frequency (Hz):")
    tone_b_label.grid(row=1, column=0, padx=5, pady=5)
    tone_b_combobox = ttk.Combobox(frame, values=tone_frequencies, state="readonly")
    tone_b_combobox.grid(row=1, column=1, padx=5, pady=5)

    generate_button = ttk.Button(frame, text="Generate and Play Tones", command=generate_and_play_tones)
    generate_button.grid(row=2, column=0, columnspan=2, padx=5, pady=5)

    info_alert_button = ttk.Button(frame, text="Info Alert", command=play_info_alert)
    info_alert_button.grid(row=2, column=5, columnspan=2, padx=5, pady=5)

    info_cancel_button = ttk.Button(frame, text="Cancel Alert", command=play_cancel_alert)
    info_cancel_button.grid(row=2, column=10, columnspan=2, padx=5, pady=5)


def play_info_alert():
    playsound(config["softwareDirectory"] + 'sounds/info_tone.wav')


def play_cancel_alert():
    playsound(config["softwareDirectory"] + 'sounds/cancel_tone.wav')


def generate_and_play_tones():
    tone_a_freq = float(tone_a_combobox.get())
    tone_b_freq = float(tone_b_combobox.get())
    sample_rate = 44100

    t_a = numpy.linspace(0, 1, int(sample_rate), False)
    t_b = numpy.linspace(0, 4, int(4 * sample_rate), False)
    tone_a = numpy.sin(tone_a_freq * t_a * 2 * numpy.pi)
    tone_b = numpy.sin(tone_b_freq * t_b * 2 * numpy.pi)

    combined_tone = numpy.concatenate((tone_a, tone_b))

    combined_tone *= 32767 / numpy.max(numpy.abs(combined_tone))
    combined_tone = combined_tone.astype(numpy.int16)

    p2 = pyaudio.PyAudio()
    stream2 = p2.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, output=True)

    stream2.write(combined_tone)

    stream2.stop_stream()
    stream2.close()
    p2.terminate()


def init_serial(port, baudrate=9600):
    return serial.Serial(port, baudrate, timeout=1)


async def control_light_switch(ip_address, command):
    plug = SmartPlug(ip_address)
    try:
        await plug.update()
        if command == "on":
            await plug.turn_on()
        elif command == "off":
            await plug.turn_off()
    except Exception as e:
        print(f"Error controlling KASA Switch at {ip_address}: {e}")


async def control_kasa_light_strip(device_ip, brightness, color, state):
    bulb = SmartLightStrip(device_ip)

    try:
        await bulb.update()
        if state == "on":
            await bulb.turn_on()
            await bulb.set_brightness(brightness)
            await bulb.set_hsv(color[0], color[1], color[2])
        elif state == "off":
            await bulb.turn_off()
        await bulb.update()
    except Exception as e:
        print(f"Error controlling KASA LED light strip at {device_ip}: {e}")


def flash_background(frame):
    flash_duration = 5000
    flash_interval = 350
    end_time = time.time() + flash_duration / 1000
    style = ttk.Style()

    def change_color():
        if time.time() > end_time:
            style.configure('Flash.TFrame', background='SystemButtonFace')
            return
        current_color = style.lookup('Flash.TFrame', 'background')
        new_color = 'red' if current_color != 'red' else 'SystemButtonFace'
        style.configure('Flash.TFrame', background=new_color)
        frame.after(flash_interval, change_color)

    frame.configure(style='Flash.TFrame')
    change_color()


def parse_relay_response(response):
    for state, relays in RESPONSES.items():
        for relay_num, relay_response in relays.items():
            if relay_response == response:
                return relay_num, state
    return None, None


def compute_checksum(byte_array):
    cmd_bytes = byte_array.copy()
    return sum(cmd_bytes) & 0xFF


def send_command(ser, command, relay_num=None):
    if not relay_num:
        raise ValueError("Relay number must be specified")

    cmd_bytes = COMMANDS[command][relay_num]

    cmd_bytes.append(compute_checksum(cmd_bytes))

    ser.write(cmd_bytes)
    response = ser.read(8)
    parsedResponse = parse_status_response(response)
    print(f"Sent command: {command} for relay {relay_num}, Response: {parsedResponse}")
    return response


def parse_status_response(response):
    statuses = {}

    if len(response) != 8:
        print(f"Unexpected response length: {len(response)}. Expected 8 bytes.")
        return statuses

    relay_num, state = parse_relay_response(response)
    if relay_num and state:
        statuses[relay_num] = state

    return statuses


def convertToBase64(data):
    base64_encoded = base64.b64encode(data)

    return f"data:audio/wav;base64,{base64_encoded.decode('utf-8')}"


async def save_audio_clip(dept_info):
    frames = []

    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M")
    audio_filename = f"{current_datetime}"

    print("Recording 25-second audio clip...")
    for _ in range(int(44100 / chunk * 25)):
        data = stream.read(chunk)
        frames.append(data)

    print("Finished recording.")

    audio_file_path_wav = os.path.join("audio_clips", f"{audio_filename}.wav")
    audio_file_path_mp3 = os.path.join("audio_clips", f"{audio_filename}.mp3")
    os.makedirs("audio_clips", exist_ok=True)

    wf = wave.open(audio_file_path_wav, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(44100)
    wf.writeframes(b''.join(frames))
    wf.close()

    audio_segment = AudioSegment.from_wav(audio_file_path_wav)

    alert_audio = AudioSegment.from_wav("Minitor_alert.wav")

    final_audio = alert_audio + audio_segment

    final_audio.export(audio_file_path_mp3, format="mp3")
    hostUrl = config["hostUrl"]
    if config["serial"]["enable"] and not dept_info["relayNumber"] == 0:
        send_command(ser, "off", dept_info["relayNumber"])

    if config["smartHome"]["enable"]:
        switch_tasks = []
        bulb_tasks = []

        for device in dept_info["smartHomeDevices"]:
            if device["type"] == "switch":
                switch_task = asyncio.create_task(
                    control_light_switch(device['ip'], 'off'))
                switch_tasks.append(switch_task)
            elif device["type"] == "bulb":
                bulb_task = asyncio.create_task(
                    control_kasa_light_strip(device["ip"], 1, (0, 100, 40), "off"))
                bulb_tasks.append(bulb_task)

        await asyncio.gather(*bulb_tasks, *switch_tasks)

    for user in dept_info['users']:
        phoneCall(f"{hostUrl}{current_datetime}.mp3", user['phone'], user['name'])

    return audio_file_path_wav


def sendDiscordWebhook(dept_id):
    if (config["discord"]["enable"]):
        current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M")
        hostUrl = config["hostUrl"]
        message = f"New off duty alert triggered for {dept_id}. Info: " + f"{hostUrl}{current_datetime}.wav"
        webhook_url = config["discord"]["url"]

        payload = {
            "content": message
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(webhook_url, json=payload, headers=headers)

        if response.status_code == 204:
            print("Discord webhook sent successfully")
        else:
            print("Failed to send Discord webhook")


def sendText(date_url, to, name):
    if (config["twilio"]["enable"]):
        current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M")

        textClient = Client(account_sid, auth_token)
        message = textClient.messages \
            .create(
            body="New off duty alert for " + name + ". Listen to call info: " + date_url + "       (Allow up to 20 seconds for audio to be available)",
            from_=config["twilio"]["from"],
            to=to
        )


def phoneCall(date_url, to, name):
    if (config["twilio"]["enable"]):
        client = Client(account_sid, auth_token)

        call = client.calls.create(
            url=date_url,
            to=to,
            from_=config["twilio"]["from"]
        )


def sendEmail(date_url, to, name):
    if (config["socketLabs"]["enable"]):
        message = BasicMessage()
        message.subject = "New Off Duty Alert"
        message.html_body = "New off duty alert for " + name + ". Call details here: " + date_url + "       (Allow up to 25 seconds for audio to be available)"
        message.plain_text_body = "New off duty alert for " + name + ". Call details here: " + date_url + "       (Allow up to 25 seconds for audio to be available)"
        message.from_email_address = EmailAddress(config["socketLabs"]["from"])
        message.to_email_address.append(EmailAddress(to))
        response = client.send(message)


def activateAlert(user, dept_id):
    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M")

    hostUrl = config["hostUrl"]
    sendText(
        f"{hostUrl}{current_datetime}.wav",
        user['phone'],
        user['name']
    )
    sendEmail(
        f"{hostUrl}{current_datetime}.wav",
        user['email'],
        user['name']
    )
    time.sleep(1)


def play_sound_and_bridge(audio_file_path):
    playsound(audio_file_path)

    bridge_stream = p.open(format=pyaudio.paInt16,
                           channels=1,
                           rate=44100,
                           input=True,
                           output=True,
                           frames_per_buffer=chunk)

    start_time = time.time()

    while time.time() - start_time < 25:
        data = bridge_stream.read(chunk)
        bridge_stream.write(data, chunk)

    bridge_stream.stop_stream()
    bridge_stream.close()
    print("Finished bridging audio.")


def setup_user_management_tab(frame, root):
    global selected_user_name_var, selected_user_email_var, selected_user_phone_var, selected_dept_var, user_listbox

    selected_user_name_var = tk.StringVar(root)
    selected_user_email_var = tk.StringVar(root)
    selected_user_phone_var = tk.StringVar(root)
    selected_dept_var = tk.StringVar(root)

    ttk.Label(frame, text="User Management").grid(row=0, column=0, padx=5, pady=5)

    user_listbox = Listbox(frame, height=15, width=50)
    user_listbox.grid(row=1, column=0, padx=5, pady=5, rowspan=4)
    user_listbox.bind('<<ListboxSelect>>', on_user_select)

    ttk.Label(frame, text="Name:").grid(row=1, column=1, padx=5, pady=5, sticky='e')
    user_name_entry = ttk.Entry(frame, textvariable=selected_user_name_var)
    user_name_entry.grid(row=1, column=2, padx=5, pady=5, sticky='we')

    ttk.Label(frame, text="Email:").grid(row=2, column=1, padx=5, pady=5, sticky='e')
    user_email_entry = ttk.Entry(frame, textvariable=selected_user_email_var)
    user_email_entry.grid(row=2, column=2, padx=5, pady=5, sticky='we')

    ttk.Label(frame, text="Phone:").grid(row=3, column=1, padx=5, pady=5, sticky='e')
    user_phone_entry = ttk.Entry(frame, textvariable=selected_user_phone_var)
    user_phone_entry.grid(row=3, column=2, padx=5, pady=5, sticky='we')

    def save_to_yaml(data, filename):
        with open(filename, 'w') as file:
            yaml.dump(data, file)

    def refresh_user_listbox(user_listbox):
        user_listbox.delete(0, 'end')
        for dept_id, dept_info in departments.items():
            user_listbox.insert('end', f"Department {dept_id}")
            for user in dept_info['users']:
                user_listbox.insert('end', f"  {user['name']} - {user['email']} - {user['phone']}")

    def update_user(dept_id, old_user_info, new_user_info):
        for user in departments[dept_id]['users']:
            if user['name'] == old_user_info['name'] and user['email'] == old_user_info['email']:
                user.update(new_user_info)
                break
        save_to_yaml(departments, 'db.yml')
        refresh_user_listbox(user_listbox)

    def delete_user(dept_id, user_info):
        departments[dept_id]['users'] = [
            user for user in departments[dept_id]['users']
            if user['name'] != user_info['name'] or user['email'] != user_info['email']
        ]
        save_to_yaml(departments, 'db.yml')
        refresh_user_listbox(user_listbox)

    def save_user_changes():
        selected_user = {
            'name': selected_user_name_var.get(),
            'email': selected_user_email_var.get(),
            'phone': selected_user_phone_var.get()
        }
        updated_user = {
            'name': user_name_entry.get(),
            'email': user_email_entry.get(),
            'phone': user_phone_entry.get()
        }
        selected_dept_id = selected_dept_var.get()

        for user in departments[selected_dept_id]['users']:
            if user['name'] == selected_user['name'] and user['email'] == selected_user['email']:
                user['name'] = updated_user['name']
                user['email'] = updated_user['email']
                user['phone'] = updated_user['phone']
                break

        save_to_yaml(departments, 'db.yml')
        refresh_user_listbox(user_listbox)

    def delete_selected_user():
        selected_user = {
            'name': selected_user_name_var.get(),
            'email': selected_user_email_var.get(),
            'phone': selected_user_phone_var.get()
        }
        selected_dept_id = selected_dept_var.get()

        departments[selected_dept_id]['users'] = [
            user for user in departments[selected_dept_id]['users']
            if not (user['name'] == selected_user['name'] and user['email'] == selected_user['email'])
        ]

        save_to_yaml(departments, 'db.yml')
        refresh_user_listbox(user_listbox)

    save_changes_button = ttk.Button(frame, text="Save Changes", command=save_user_changes)
    save_changes_button.grid(row=5, column=2, padx=5, pady=5, sticky='e')

    remove_user_button = ttk.Button(frame, text="Remove User", command=delete_selected_user)
    remove_user_button.grid(row=5, column=2, padx=5, pady=5, sticky='w')

    ttk.Label(frame, text="Select Department:").grid(row=0, column=2, padx=5, pady=5, sticky='e')
    dept_dropdown = ttk.Combobox(frame, textvariable=selected_dept_var, state="readonly")
    dept_dropdown['values'] = list(departments.keys())
    dept_dropdown.grid(row=0, column=3, padx=5, pady=5, sticky='w')

    refresh_user_listbox(user_listbox)


def on_user_select(event):
    try:
        index = user_listbox.curselection()[0]
        selected_item = user_listbox.get(index)

        selected_user_name_var.set('')
        selected_user_email_var.set('')
        selected_user_phone_var.set('')

        if ' - ' in selected_item:
            user_details = selected_item.strip().split(' - ')
            # print(user_details)
            selected_user_name_var.set(user_details[0].strip(' -'))
            selected_user_email_var.set(user_details[1].strip())
            selected_user_phone_var.set(user_details[2].strip())

    except IndexError:
        pass


def schmitt(data, rate):
    loudness = numpy.sqrt(numpy.sum((data / 32768.) ** 2)) / float(len(data))
    rms = 20.0 * numpy.log10(loudness)
    if rms < SQUELCH:
        return -1

    blockSize = len(data) - 1

    freq = 0.
    trigfact = 0.6

    schmittBuffer = data

    A1 = max(schmittBuffer)
    A2 = min(schmittBuffer)

    t1 = round(A1 * trigfact)
    t2 = round(A2 * trigfact)

    startpoint = -1
    endpoint = 0
    schmittTriggered = 0
    tc = 0
    for j in range(0, blockSize):
        if not schmittTriggered:
            schmittTriggered = (schmittBuffer[j] >= t1)
        elif schmittBuffer[j] >= t2 and schmittBuffer[j + 1] < t2:
            schmittTriggered = 0
            if startpoint == -1:
                tc = 0
                startpoint = j
                endpoint = startpoint + 1
            else:
                endpoint = j
                tc += 1

    if endpoint > startpoint:
        freq = rate * (tc / float(endpoint - startpoint))

    return freq


def isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


alert_queue = queue.Queue()


async def measure_tones():
    chunk = 2048
    initial_tone_time = None

    if len(sys.argv) > 1:
        wavfile = sys.argv[1]
    else:
        wavfile = ''

    if not wavfile:
        pa = pyaudio.PyAudio()
        input_device_index = pa.get_default_host_api_info()['defaultInputDevice']
        #  print(input_device_index)
        FORMAT = pyaudio.paInt16
        channels = 1
        rate = 44100

        stream = pa.open(format=FORMAT,
                         channels=channels,
                         rate=rate,
                         input=True,
                         # output=True,
                         #                 input_device_index=input_device_index,
                         frames_per_buffer=chunk)
    else:
        import wave
        wav = wave.open(wavfile, 'r')
        rate = wav.getframerate()
        channels = wav.getnchannels()

    freqBufferSize = int(MIN_TONE_LENGTH * rate / float(chunk))
    freqBuffer = numpy.zeros(freqBufferSize)
    freqIndex = 0
    lastFreq = 0.
    toneIndex = -1
    tone1 = 0.0
    tone2 = 0.0
    while True:
        if not wavfile:
            data = stream.read(chunk)
        else:
            data = wav.readframes(chunk)
            if wav.tell() >= wav.getnframes():
                break

        buf = numpy.frombuffer(data, dtype=numpy.int16)
        if channels == 2:
            buf = buf.reshape(-1, 2)
            buf = numpy.delete(buf, 1, axis=1)
            buf = buf.reshape(-1)

        freq = schmitt(buf, rate)

        if (freq > 0) and (freq > 200.0):
            freqBuffer[freqIndex % freqBufferSize] = freq
            freqIndex += 1
            stddev = freqBuffer.std()

            if stddev < MAX_TONE_FREQ_STD_DEVIATION:
                mean = freqBuffer.mean()
                if abs(mean - lastFreq) > MIN_TONE_FREQUENCY_DIFFERENCE:
                    toneIndex = (toneIndex + 1) % NUM_TONES
                    if toneIndex == 0:
                        print("Reset")
                    lastFreq = mean
                    print("Detected Frequency: {:.2f} Hz (Tone {})".format(mean, toneIndex + 1))

                    if (toneIndex + 1 == 1):
                        tone1 = mean
                        initial_tone_time = time.time()
                    elif (toneIndex + 1 == 2):
                        tone2 = mean
                    else:
                        print("Tone out of sync detected. Resetting tones")
                    print("Detected: " + str(tone1) + " : " + str(tone2))
                    # tone1_box.state([tk.NORMAL])
                    # tone2_box.state([tk.NORMAL])
                    tone1_box.delete(0, tk.END)
                    tone2_box.delete(0, tk.END)
                    tone1_box.insert(tk.END, str(round(tone1, 1)))
                    tone2_box.insert(tk.END, str(round(tone2, 1)))
                    # tone1_box.state(['disabled'])
                    # tone2_box.state(['disabled'])

                    # print("INITIAL TONE: " + str(initial_tone_time))
                    # print("TIME: " + str(time.time()))
                    # print("TIME - INITIAL" + str(initial_tone_time - time.time() < 1.5 ))
                    if not config["disableAlerting"]:
                        for dept_id, dept_info in departments.items():
                            tone1_db = dept_info['tone1']
                            tone2_db = dept_info['tone2']

                            if isclose(tone1, tone1_db, abs_tol=15.0) and isclose(tone2, tone2_db, abs_tol=15.0):
                                if config["serial"]["enable"]:
                                    send_command(ser, "on", dept_info["relayNumber"])

                                if config["smartHome"]["enable"]:
                                    if 'smartHomeDevices' in dept_info:
                                        if config["smartHome"]["enable"]:
                                            switch_tasks = []
                                            bulb_tasks = []

                                            for device in dept_info["smartHomeDevices"]:
                                                if device["type"] == "switch":
                                                    print("here")
                                                    switch_task = asyncio.create_task(
                                                        control_light_switch(device['ip'], 'on'))
                                                    switch_tasks.append(switch_task)
                                                elif device["type"] == "bulb":
                                                    print("here2")
                                                    bulb_task = asyncio.create_task(
                                                        control_kasa_light_strip(device["ip"], 100,
                                                                                 (0, 100, 40), "on"))
                                                    bulb_tasks.append(bulb_task)

                                            print("here3")

                                            await asyncio.gather(*bulb_tasks, *switch_tasks)

                                # put it in the queue
                                activeAlert.insert(tk.END, "ALERT -- DEPT ID: " + dept_id + " -- A: " + str(
                                    dept_info['tone1']) + " B: " + str(dept_info['tone2']) + "\n")
                                flash_background(alert_frame)
                                alert_queue.put((dept_id, dept_info))

        if initial_tone_time and (time.time() - initial_tone_time > 4):
            # print("Tone out of sync detect. Reset.")
            tone1 = 0.0
            tone2 = 0.0
            toneIndex = -1
            initial_tone_time = None


async def handle_alerts():
    while True:
        dept_id, dept_info = alert_queue.get()

        if config['localAudioAlert']:
            alert_thread = threading.Thread(target=play_sound_and_bridge,
                                            args=(config["softwareDirectory"] + "Minitor_alert.wav",))
            alert_thread.start()

        sendDiscordWebhook(dept_id)

        if (config["serial"]["enable"] and not dept_info["relayNumber"] == 0):
            send_command(ser, "on", dept_info["relayNumber"])
            for user in dept_info['users']:
                activateAlert(user, dept_id)
        audio_path_wav = await save_audio_clip(dept_info)

        alert_queue.task_done()


if __name__ == "__main__":
    try:
        all_statuses = {}
        root = tk.Tk()
        if (config["smallScreen"]):
            root.geometry("480x320")
        else:
            root.geometry("2000x1000")
        # root.attributes("-fullscreen", True)
        root.title("Tone Alert System")

        setup_gui(root)

        if (config["serial"]["enable"]):
            ser = init_serial(config["serial"]["port"])

        tone_detection_thread = threading.Thread(target=lambda: asyncio.run(measure_tones()))
        tone_detection_thread.daemon = True
        tone_detection_thread.start()

        handle_alerts_thread = threading.Thread(target=lambda: asyncio.run(handle_alerts()))
        handle_alerts_thread.daemon = True
        handle_alerts_thread.start()

        root.mainloop()

    except KeyboardInterrupt:
        print("Exiting")
    finally:
        p.terminate()
