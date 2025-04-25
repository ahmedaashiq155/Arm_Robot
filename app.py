from flask import Flask, jsonify, render_template, request
import os
from openai import OpenAI
import json
import cv2
from dotenv import load_dotenv
import base64

load_dotenv()

app = Flask(__name__)

api_key = "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"
client = OpenAI(api_key=api_key)

COMMAND_TO_SERIAL = {
    "pickup": 1,
    "high five": 5
}

@app.route('/')
def home():     
    return render_template('index.html')

@app.route('/save-audio', methods=['POST'])
def save_audio():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
        
    audio = request.files['audio']
    os.makedirs('src', exist_ok=True)
    audio_path = os.path.join('src', 'Recording.m4a')
    audio.save(audio_path)
    
    return jsonify({"success": True, "filename": "Recording.m4a"})

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        capture_image()
        transcript_text = process_audio()
        save_transcript(transcript_text)
        
        return jsonify({"text": transcript_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def capture_image():
    cam = cv2.VideoCapture(0)
    ret, frame = cam.read()
    
    if ret:
        os.makedirs('src', exist_ok=True)
        photo_path = os.path.join('src', 'Recording.jpg')
        cv2.imwrite(photo_path, frame)
    
    cam.release()

def process_audio():
    file_path = os.path.join('src', 'Recording.m4a')
    if not os.path.exists(file_path):
        raise FileNotFoundError("No audio file found")
        
    with open(file_path, 'rb') as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    
    return transcription.text

def save_transcript(transcript_text):
    transcript_data = {"text": transcript_text}
    
    os.makedirs('output', exist_ok=True)
    json_path = os.path.join('output', "transcript.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)

@app.route('/processing', methods=['POST'])
def processing():
    try:
        transcript_text, image_data = load_data()
        result = analyze_with_ai(transcript_text, image_data)
        serial_code = COMMAND_TO_SERIAL.get(result, 0)
        
        save_command(result)
        send_to_arduino(serial_code)
            
        return jsonify({"command": result, "serial_code": serial_code})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def load_data():
    transcript_path = os.path.join('output', 'transcript.json')
    image_path = os.path.join('src', 'Recording.jpg')
    
    if not os.path.exists(transcript_path) or not os.path.exists(image_path):
        raise FileNotFoundError("Files not found")
        
    with open(transcript_path, 'r') as f:
        transcript_data = json.load(f)
        transcript_text = transcript_data.get('text', '')
        
    with open(image_path, 'rb') as img_file:
        image_data = base64.b64encode(img_file.read()).decode('utf-8')
        
    return transcript_text, image_data

def analyze_with_ai(transcript_text, image_data):
    messages = [
        {
            "role": "system", 
            "content": "You are an assistant that processes images and transcriptions to interpret commands for a robotic arm. Analyze the transcription and identify which of these commands the user intends: 'pickup' or 'high five'. Even if the user phrases it differently (like 'can you pick up that object' or 'give me a high five'), extract just the core command. Your response should only be one of these exact command words without any explanation or additional text."
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"Process this image along with the following transcription: {transcript_text}"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                }
            ]
        }
    ]
    
    response = client.chat.completions.create(
        model="o4-mini",
        messages=messages,
    )
    
    return response.choices[0].message.content.strip().lower()

def save_command(command):
    os.makedirs('output', exist_ok=True)
    output_path = os.path.join('output', 'command_output.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({"command": command}, f, ensure_ascii=False, indent=2)

def send_to_arduino(serial_code):
    try:
        import serial
        ser = serial.Serial('COM3', 9600, timeout=1)
        ser.write(str(serial_code).encode())
        ser.close()
    except Exception:
        pass

@app.route('/get_serial_command', methods=['GET'])
def get_serial_command():
    try:
        output_path = os.path.join('output', 'command_output.json')
        if not os.path.exists(output_path):
            return jsonify({"error": "No command available"}), 404
            
        with open(output_path, 'r') as f:
            output_data = json.load(f)
            command = output_data.get('command', '')
            
        serial_code = COMMAND_TO_SERIAL.get(command, 0)
        
        return str(serial_code), 200, {'Content-Type': 'text/plain'}
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
