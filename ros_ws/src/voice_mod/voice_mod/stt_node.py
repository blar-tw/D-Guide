from google.cloud import speech_v1 as speech  
import pyaudio, base64, io

RATE = 16000
CHANNELS = 1
CHUNK = 1024
RECORD_SEC = 5

p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

frames = [stream.read(CHUNK, exception_on_overflow=False)
          for _ in range(int(RATE / CHUNK * RECORD_SEC))]

stream.stop_stream(); stream.close(); p.terminate()

client = speech.SpeechClient()      # uses GOOGLE_APPLICATION_CREDENTIALS
audio = speech.RecognitionAudio(content=b''.join(frames))
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=RATE,
    language_code="zh-TW",
)

response = client.recognize(config=config, audio=audio)
for result in response.results:
    print("辨識結果:", result.alternatives[0].transcript)







"""def handle_request(request, response):
    print("Voice processing started...")
    # do whisper + llm + tts
    response.success = True
    response.message = "Voice interaction complete"
    return response
    最後的最後整個模組做完才會回傳 response給ww_node
"""