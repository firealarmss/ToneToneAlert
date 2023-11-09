# Portions of this software Copyright https://github.com/syastrov/twotonedecoder
NUM_TONES = 2
MIN_TONE_FREQUENCY_DIFFERENCE = 10.0
MIN_TONE_LENGTH = 1.000
MAX_TONE_FREQ_STD_DEVIATION = 15.0
SQUELCH = -70.

import sys
import threading
import queue


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
                #output=True,
                frames_per_buffer=chunk)


#
# requests.post('https://api.mynotifier.app', {
#     "apiKey": 'd2953cdb-7737-40da-b502-bbc689594bcf',
#     "message": "Our first notification!",
#     "description": "This is cool",
#     "type": "warning", # info, error, warning or success
# })

def init_serial(port, baudrate=9600):
    return serial.Serial(port, baudrate, timeout=1)


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


def save_audio_clip(dept_info):
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
    if (config["serial"]["enable"] and not dept_info["relayNumber"] == 0):
        send_command(ser, "off", dept_info["relayNumber"])
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

    print("Alert!")
    hostUrl = config["hostUrl"]
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

def measure_tones():
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
                         #output=True,
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

        buf = numpy.fromstring(data, dtype=numpy.int16)
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

                    # print("INITIAL TONE: " + str(initial_tone_time))
                    # print("TIME: " + str(time.time()))
                    # print("TIME - INITIAL" + str(initial_tone_time - time.time() < 1.5 ))
                    for dept_id, dept_info in departments.items():
                        tone1_db = dept_info['tone1']
                        tone2_db = dept_info['tone2']

                        if isclose(tone1, tone1_db, abs_tol=15.0) and isclose(tone2, tone2_db, abs_tol=15.0):
                            # Instead of directly handling the alert, put it in the queue
                            alert_queue.put((dept_id, dept_info))

        if initial_tone_time and (time.time() - initial_tone_time > 4):
            # print("Tone out of sync detect. Reset.")
            tone1 = 0.0
            tone2 = 0.0
            toneIndex = -1
            initial_tone_time = None

def handle_alerts():
    while True:
        dept_id, dept_info = alert_queue.get()

        if config['localAudioAlert']:
            alert_thread = threading.Thread(target=play_sound_and_bridge,
                                            args=("E:/ToneTonePage/Minitor_alert.wav",))
            alert_thread.start()

            sendDiscordWebhook(dept_id)

        if (config["serial"]["enable"] and not dept_info["relayNumber"] == 0):
            send_command(ser, "on", dept_info["relayNumber"])
            for user in dept_info['users']:
                activateAlert(user, dept_id)
        audio_path_wav = save_audio_clip(dept_info)

        alert_queue.task_done()

   # if not wavfile:
   #     stream.close()
   #     pa.terminate()
   # else:
   #     wav.close()


if __name__ == "__main__":
    try:
        all_statuses = {}
        if (config["serial"]["enable"]):
            ser = init_serial(config["serial"]["port"])

        tone_detection_thread = threading.Thread(target=measure_tones)
        tone_detection_thread.daemon = True
        tone_detection_thread.start()

        handle_alerts()

    except KeyboardInterrupt:
        print("Exiting")
    finally:
        p.terminate()
