"""
Async video screening — Jenny sends candidates a link to record
3 video answers on their own time. No scheduling needed.
Candidate opens the page, records in their browser, submits.
Jenny evaluates the responses automatically.
"""

import os
import json
from jenny.persona import JENNY_NAME, COMPANY_NAME, JENNY_FULL_NAME
from config import get_ai_client
import airtable_ats as ats

ASYNC_VIDEO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Video Interview — {company}</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,sans-serif; background:#0f1e3d; min-height:100vh;
        display:flex; align-items:center; justify-content:center; padding:20px; }}
.container {{ background:white; border-radius:16px; max-width:700px; width:100%;
              overflow:hidden; box-shadow:0 30px 80px rgba(0,0,0,.4); }}
.header {{ background:linear-gradient(135deg,#0f1e3d,#2563eb); color:white;
           padding:28px 32px; }}
.header h1 {{ font-size:20px; font-weight:800; }}
.header p  {{ font-size:13px; opacity:.7; margin-top:4px; }}
.jenny-intro {{ display:flex; gap:16px; align-items:flex-start; padding:24px 32px;
                border-bottom:1px solid #e2e8f0; background:#f8fafc; }}
.jenny-avatar {{ width:52px; height:52px; border-radius:50%;
                 background:linear-gradient(135deg,#0f1e3d,#2563eb);
                 color:white; display:flex; align-items:center; justify-content:center;
                 font-weight:800; font-size:20px; flex-shrink:0; }}
.jenny-text {{ font-size:13px; line-height:1.7; color:#334155; }}
.jenny-text strong {{ color:#0f1e3d; }}
.body {{ padding:24px 32px; }}
.question-block {{ margin-bottom:28px; padding:20px; background:#f8fafc;
                   border-radius:10px; border-left:4px solid #2563eb; }}
.q-label {{ font-size:11px; font-weight:700; text-transform:uppercase;
            letter-spacing:.5px; color:#64748b; margin-bottom:6px; }}
.q-text  {{ font-size:15px; font-weight:700; color:#0f172a; margin-bottom:14px; }}
.video-area {{ position:relative; background:#1e293b; border-radius:8px;
               overflow:hidden; aspect-ratio:16/9; }}
video {{ width:100%; height:100%; display:block; }}
.controls {{ display:flex; gap:10px; margin-top:10px; justify-content:center; }}
.btn {{ padding:9px 20px; border-radius:7px; font-weight:700; font-size:13px;
        border:none; cursor:pointer; transition:all .15s; }}
.btn-record {{ background:#dc2626; color:white; }}
.btn-record:hover {{ background:#b91c1c; }}
.btn-stop   {{ background:#64748b; color:white; display:none; }}
.btn-retry  {{ background:#f1f5f9; color:#334155; display:none; }}
.recording-badge {{ display:none; position:absolute; top:12px; left:12px;
                    background:rgba(220,38,38,.9); color:white; padding:4px 10px;
                    border-radius:20px; font-size:11px; font-weight:700; }}
.recording-badge.active {{ display:block; }}
.status {{ font-size:12px; color:#64748b; text-align:center; margin-top:6px; height:18px; }}
.submit-section {{ padding:0 32px 28px; text-align:center; }}
.btn-submit {{ background:linear-gradient(135deg,#1d4ed8,#2563eb); color:white;
               padding:13px 40px; font-size:15px; border-radius:8px; width:100%;
               border:none; cursor:pointer; font-weight:700; }}
.btn-submit:disabled {{ opacity:.5; cursor:not-allowed; }}
.progress {{ display:flex; gap:8px; justify-content:center; margin:0 32px 20px;
             flex-wrap:wrap; }}
.prog-dot {{ width:10px; height:10px; border-radius:50%; background:#e2e8f0; transition:.3s; }}
.prog-dot.done {{ background:#16a34a; }}
.prog-dot.active {{ background:#2563eb; }}
.success-screen {{ display:none; text-align:center; padding:60px 32px; }}
.success-screen h2 {{ font-size:24px; font-weight:800; color:#0f172a; margin:16px 0 8px; }}
.success-screen p  {{ color:#64748b; font-size:14px; line-height:1.7; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{company} — Video Interview</h1>
    <p>{job_title}</p>
  </div>
  <div class="jenny-intro">
    <div class="jenny-avatar">J</div>
    <div class="jenny-text">
      <strong>Hi {candidate_first_name}, I'm {jenny_name}!</strong><br>
      I'm the AI recruiting assistant for {company}. This quick video interview has
      {num_questions} short questions — takes about 10-15 minutes total.
      Record each answer when you're ready. You can re-record as many times as you like.
      <br><br><em>Tip: Find a quiet spot with good lighting. You've got this! 🎥</em>
    </div>
  </div>

  <div class="body">
    <div class="progress" id="progress"></div>
    <div id="questions-container"></div>
  </div>

  <div class="submit-section">
    <button class="btn-submit" id="submit-btn" disabled onclick="submitInterview()">
      Submit My Interview →
    </button>
    <p style="font-size:11px;color:#94a3b8;margin-top:8px">
      By submitting, you agree to your responses being reviewed by our recruiting team.
    </p>
  </div>

  <div class="success-screen" id="success">
    <div style="font-size:64px">🎉</div>
    <h2>You're all done!</h2>
    <p>Thanks {candidate_first_name}! {jenny_name} will review your responses and
    the team will be in touch within 24-48 hours.<br><br>
    <strong>Fingers crossed! 🤞</strong></p>
  </div>
</div>

<script>
const QUESTIONS = {questions_json};
const RECORD_ID = '{record_id}';
const JOB_TITLE = '{job_title}';
const blobs = {{}};

// Build UI
const progress = document.getElementById('progress');
const container = document.getElementById('questions-container');

QUESTIONS.forEach((q, i) => {{
  progress.innerHTML += `<div class="prog-dot ${{i===0?'active':''}}" id="dot-${{i}}"></div>`;
  container.innerHTML += `
    <div class="question-block" id="qblock-${{i}}" style="${{i>0?'display:none':''}}">
      <div class="q-label">Question ${{i+1}} of ${{QUESTIONS.length}}</div>
      <div class="q-text">${{q}}</div>
      <div class="video-area">
        <video id="preview-${{i}}" autoplay muted playsinline></video>
        <video id="playback-${{i}}" playsinline controls style="display:none"></video>
        <div class="recording-badge" id="badge-${{i}}">⏺ RECORDING</div>
      </div>
      <div class="controls">
        <button class="btn btn-record" id="rec-${{i}}" onclick="startRecording(${{i}})">▶ Start Recording</button>
        <button class="btn btn-stop"   id="stop-${{i}}" onclick="stopRecording(${{i}})">⏹ Stop</button>
        <button class="btn btn-retry"  id="retry-${{i}}" onclick="retryRecording(${{i}})">↺ Re-record</button>
        ${{i < QUESTIONS.length-1
          ? `<button class="btn" style="background:#e2e8f0;color:#334155;display:none" id="next-${{i}}" onclick="nextQuestion(${{i}})">Next Question →</button>`
          : ''}}
      </div>
      <div class="status" id="status-${{i}}">Click "Start Recording" when ready</div>
    </div>`;
}});

let mediaRecorder, stream, chunks = [];

async function startRecording(i) {{
  stream = await navigator.mediaDevices.getUserMedia({{video:true, audio:true}});
  document.getElementById('preview-'+i).srcObject = stream;
  document.getElementById('playback-'+i).style.display = 'none';
  document.getElementById('preview-'+i).style.display = 'block';
  chunks = [];
  mediaRecorder = new MediaRecorder(stream, {{mimeType:'video/webm;codecs=vp8,opus'}});
  mediaRecorder.ondataavailable = e => {{ if(e.data.size>0) chunks.push(e.data); }};
  mediaRecorder.onstop = () => {{
    blobs[i] = new Blob(chunks, {{type:'video/webm'}});
    const url = URL.createObjectURL(blobs[i]);
    document.getElementById('playback-'+i).src = url;
    document.getElementById('playback-'+i).style.display = 'block';
    document.getElementById('preview-'+i).style.display = 'none';
    document.getElementById('status-'+i).textContent = '✓ Recorded! Watch it back above.';
    document.getElementById('retry-'+i).style.display = 'inline-flex';
    document.getElementById('stop-'+i).style.display = 'none';
    if (document.getElementById('next-'+i)) document.getElementById('next-'+i).style.display = 'inline-flex';
    document.getElementById('badge-'+i).classList.remove('active');
    checkAllRecorded();
    stream.getTracks().forEach(t => t.stop());
  }};
  mediaRecorder.start();
  document.getElementById('badge-'+i).classList.add('active');
  document.getElementById('rec-'+i).style.display = 'none';
  document.getElementById('stop-'+i).style.display = 'inline-flex';
  document.getElementById('status-'+i).textContent = 'Recording… speak clearly!';
}}

function stopRecording(i) {{ mediaRecorder.stop(); }}

function retryRecording(i) {{
  delete blobs[i];
  document.getElementById('retry-'+i).style.display = 'none';
  if (document.getElementById('next-'+i)) document.getElementById('next-'+i).style.display = 'none';
  document.getElementById('rec-'+i).style.display = 'inline-flex';
  document.getElementById('playback-'+i).style.display = 'none';
  document.getElementById('status-'+i).textContent = 'Click "Start Recording" when ready';
  checkAllRecorded();
}}

function nextQuestion(i) {{
  document.getElementById('qblock-'+i).style.display = 'none';
  document.getElementById('qblock-'+(i+1)).style.display = 'block';
  document.getElementById('dot-'+i).className = 'prog-dot done';
  document.getElementById('dot-'+(i+1)).className = 'prog-dot active';
}}

function checkAllRecorded() {{
  const all = QUESTIONS.every((_, i) => !!blobs[i]);
  document.getElementById('submit-btn').disabled = !all;
}}

async function submitInterview() {{
  const btn = document.getElementById('submit-btn');
  btn.textContent = 'Uploading… please wait'; btn.disabled = true;

  const fd = new FormData();
  QUESTIONS.forEach((q, i) => {{
    if (blobs[i]) fd.append('video_'+i, blobs[i], 'q'+i+'.webm');
    fd.append('question_'+i, q);
  }});
  fd.append('record_id', RECORD_ID);
  fd.append('job_title',  JOB_TITLE);

  await fetch('/jenny/submit-video-interview', {{method:'POST', body:fd}});
  document.querySelector('.body').style.display = 'none';
  document.querySelector('.submit-section').style.display = 'none';
  document.getElementById('success').style.display = 'block';
}}
</script>
</body>
</html>"""


def get_async_interview_page(
    candidate_name: str,
    job_title: str,
    record_id: str,
    custom_questions: list[str] | None = None
) -> str:
    from jenny.zoom_bot import get_questions_for_job
    questions = custom_questions or get_questions_for_job(job_title)
    first_name = candidate_name.split()[0]
    return ASYNC_VIDEO_HTML.format(
        company=COMPANY_NAME,
        jenny_name=JENNY_NAME,
        candidate_first_name=first_name,
        job_title=job_title,
        num_questions=len(questions),
        questions_json=json.dumps(questions),
        record_id=record_id
    )


def evaluate_video_responses(questions: list[str], transcripts: list[str],
                              job_title: str) -> dict:
    """Score async video interview responses using AI."""
    client, model = get_ai_client()
    qa_text = "\n\n".join(
        f"Q{i+1}: {q}\nA{i+1}: {t}"
        for i, (q, t) in enumerate(zip(questions, transcripts))
    )
    prompt = f"""Score this candidate's async video interview responses for the {job_title} role.

{qa_text}

Return ONLY valid JSON:
{{
  "score": <1-10>,
  "recommend": "<Strong Yes|Yes|Maybe|No>",
  "summary": "<2-3 sentences>",
  "strengths": ["strength 1", "strength 2"],
  "concerns": ["concern 1"],
  "communication_score": <1-10>,
  "next_step": "<Schedule Final Interview|Follow Up|Reject>"
}}"""
    resp = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}],
        max_tokens=600, temperature=0.2
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    return json.loads(raw.strip())
