'use strict';

/*
 * Live local facial-movement research for NeuroCognition X.
 * Processing consent is independent of the separately revocable permission
 * to store sampled derived measurements. Raw video stays on this device.
 * The browser may suspend camera frames when hidden; no hidden-frame guarantee.
 */
const el = (tag, value) => {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = value;
  return node;
};

export function mountCamera(context, parent = document.body, options = {}) {
  const required = options.requiredForAssessment === true;
  const onLoss = typeof options.onLoss === 'function' ? options.onLoss : () => {};
  const panel = el('details');
  panel.className = 'camera-panel';
  panel.id = 'ncx-live-camera';
  panel.open = required;
  panel.append(el('summary', required
    ? 'Live camera monitoring · required for this research pathway'
    : 'Live camera movement research'));
  panel.append(el('p',
    'Local facial landmarks, blink coefficients and head movement are research measurements, not a diagnosis or emotion/attention detector. ' +
    'Raw video is not uploaded or recorded. Browser timing may be affected. Camera permission and processing consent are required for the camera-enabled pathway.'));

  const consent = el('input');
  consent.type = 'checkbox';
  const consentLabel = el('label');
  consentLabel.append(consent, ' I consent to live local camera processing during this session.');
  const persist = el('input');
  persist.type = 'checkbox';
  const storageLabel = el('label');
  storageLabel.append(persist, ' Save sampled *derived* measurements to my account (separate workspace permission required).');
  const startButton = el('button', 'Start / restart camera');
  const stopButton = el('button', 'Stop camera and end monitoring');
  const grantButton = el('button', 'Authorize saving derived measurements');
  grantButton.type = 'button';
  const storageHelp = el('p', 'Live camera processing requires your consent and browser camera permission. Saving derived measurements additionally requires account storage authorization. No raw video is saved.');
  storageHelp.setAttribute('role', 'note');
  const retryButton = el('button', 'Retry saving pending samples');
  const saveStatus = el('p', 'Data saving: no batches confirmed.');
  saveStatus.setAttribute('role', 'status');
  saveStatus.setAttribute('aria-live', 'polite');
  const qualityStatus = el('p', 'Camera tracking quality: no observations yet.');
  const message = el('p', required
    ? 'Camera waiting for consent. The assessment cannot start until live capture is ready.'
    : 'Camera off.');
  message.setAttribute('role', 'status');
  message.setAttribute('aria-live', 'polite');
  const video = el('video');
  video.autoplay = true;
  video.muted = true;
  video.playsInline = true;
  video.width = 240;
  const canvas = el('canvas');
  canvas.width = 320;
  canvas.height = 240;
  canvas.setAttribute('aria-label', 'Local sampled facial landmark positions');
  const ctx = canvas.getContext?.('2d');
  panel.append(consentLabel, storageLabel, storageHelp, grantButton, startButton, stopButton, video, canvas, message, qualityStatus, saveStatus, retryButton);
  parent.append(panel);

  let stream = null;
  let model = null;
  let timer = null;
  let poll = null;
  let starting = null;
  let generation = 0;
  let rows = [];
  let segment = null;
  let began = 0;
  let revision = null;
  let lastFrame = -1;
  let pending = [];
  let flushChain = Promise.resolve();
  let captureStartedAt = 0;
  let visibilityGap = false;
  let intentionalStop = false;
  let confirmedSamples = 0;
  let confirmedBatches = 0;
  let observedFrames = 0;
  let observedSingleFaceFrames = 0;
  let lastSaveError = '';

  function countPending() {
    return pending.reduce((sum, item) => sum + item.body.samples.length, 0) + rows.length;
  }
  function showSaveStatus() {
    if (!persist.checked && countPending() === 0) {
      saveStatus.textContent = 'Local-only processing: no derived measurements are being saved.';
      return;
    }
    saveStatus.textContent = 'Backend-confirmed: ' + confirmedSamples + ' samples in ' + confirmedBatches +
      ' batches · not yet saved: ' + countPending() + ' samples' +
      (lastSaveError ? ' · save failed: ' + lastSaveError : '') +
      '. Closing this page can discard unsaved measurements.';
  }
  function showQualityStatus() {
    qualityStatus.textContent = 'Face observations this capture: ' + observedSingleFaceFrames +
      ' single-face frames / ' + observedFrames + ' processed frames' +
      (visibilityGap ? ' · a hidden-tab gap occurred' : '') +
      '. Camera measurements are descriptive research observations only.';
  }

  const endpoint = (c, path) => '/api/ncx/hub/' + encodeURIComponent(c.pid) + path + '?mode=' + encodeURIComponent(c.mode);
  async function request(c, path, method = 'GET', body) {
    const response = await fetch(endpoint(c, path), {
      method,
      headers: { 'Content-Type': 'application/json', 'X-NeuroAccess-Request': '1' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const payload = await response.json();
    if (!response.ok) throw Error(typeof payload.detail === 'string' ? payload.detail : 'Camera request rejected');
    return payload;
  }
  function identity() {
    const c = context();
    return c?.pid ? {
      pid: c.pid, mode: c.mode, session_id: c.session_id || null,
      attempt_id: c.attempt_id || null,
    } : null;
  }
  function active() {
    return Boolean(stream && stream.getVideoTracks().some(track => track.readyState === 'live'));
  }
  function showStorageGuidance() {
    if (!consent.checked) {
      message.textContent = 'First consent to live local camera processing. You can refuse without enabling the camera.';
      return;
    }
    message.textContent = 'Camera storage is not authorized. Choose “Authorize saving derived measurements” or uncheck saving to use live local camera processing only.';
  }
  async function authorizeStorage() {
    if (!consent.checked) {
      showStorageGuidance();
      throw Error('camera_consent_required');
    }
    if (active()) {
      message.textContent = 'Stop camera before changing the data storage authorization, then restart.';
      throw Error('stop_camera_to_change_storage_authorization');
    }
    const participant = identity();
    if (!participant) throw Error('Select a participant before authorizing storage.');
    grantButton.disabled = true;
    try {
      // This action is initiated only by the separate user-facing authorization button.
      // Preserve all existing permission scopes; never silently broaden other scopes.
      const current = await request(participant, '/permissions');
      if (current.camera) {
        persist.checked = true;
        showSaveStatus();
        revision = current.revision;
        message.textContent = 'Derived-camera-data storage is already authorized for this participant.';
        return true;
      }
      const saved = await request(participant, '/permissions', 'PUT', {
        expected_revision: current.revision,
        screening: current.screening === true,
        daily: current.daily === true,
        camera: true,
        cross_engine: current.cross_engine === true,
      });
      if (!saved.camera || typeof saved.revision !== 'number') {
        throw Error('Camera storage authorization was not confirmed by the server.');
      }
      revision = saved.revision;
      persist.checked = true;
      showSaveStatus();
      message.textContent = 'Derived-camera-data storage authorized. You may now start live camera monitoring.';
      return true;
    } catch (error) {
      message.textContent = error.message === 'permission_changed_refresh'
        ? 'Your account permissions changed. Recheck authorization and try again.'
        : 'Could not authorize camera storage: ' + error.message;
      throw error;
    } finally {
      grantButton.disabled = false;
    }
  }
  async function savePending() {
    for (const item of [...pending]) {
      try {
        // An HTTP 2xx alone does not prove the expected batch was persisted.
        // The existing backend returns its durable record ID and sample count.
        const saved = await request(item.c, '/camera', 'POST', item.body);
        if (saved.id !== item.body.id || saved.result?.samples !== item.body.samples.length) {
          throw Error('Camera storage receipt did not match the submitted batch');
        }
        const index = pending.indexOf(item);
        if (index >= 0) {
          pending.splice(index, 1);
          confirmedSamples += item.body.samples.length;
          confirmedBatches += 1;
        }
        lastSaveError = '';
        showSaveStatus();
      } catch (error) {
        lastSaveError = String(error?.message || error);
        showSaveStatus();
        return;
      }
    }
    showSaveStatus();
  }
  function finishSegment() {
    if (rows.length && segment && persist.checked) {
      pending.push({
        c: segment,
        body: {
          id: crypto.randomUUID(),
          consent_revision: revision,
          session_id: segment.session_id,
          attempt_id: segment.attempt_id,
          model: 'mediapipe-face-landmarker-float16-v1',
          samples: rows,
          client_duration_ms: Math.max(performance.now() - began, rows.at(-1).at_ms),
        },
      });
    }
    rows = [];
    began = performance.now();
    segment = identity();
    showSaveStatus();
    flushChain = flushChain.catch(() => {}).then(savePending);
    return flushChain;
  }
  async function stop({ reason = 'user_stopped', notify = true, clearUnsent = false } = {}) {
    const wasActive = Boolean(stream);
    intentionalStop = true;
    generation++;
    clearTimeout(timer);
    clearInterval(poll);
    timer = null;
    poll = null;
    const previous = stream;
    stream = null;
    if (previous) previous.getTracks().forEach(t => t.stop());
    video.srcObject = null;
    if (clearUnsent) { rows = []; pending = []; showSaveStatus(); }
    else await finishSegment();
    if (notify && required && wasActive) onLoss(reason);
    message.textContent = pending.length
      ? 'Camera stopped. Pending derived measurements have not all been saved.'
      : 'Camera stopped. No active facial measurements.';
  }
  function discard() {
    intentionalStop = true;
    generation++;
    clearTimeout(timer);
    clearInterval(poll);
    stream?.getTracks().forEach(t => t.stop());
    stream = null;
    video.srcObject = null;
    rows = [];
    pending = [];
    model?.close();
    model = null;
  }
  async function lost(reason) {
    if (!active() && !stream) return;
    await stop({ reason, notify: true });
  }
  async function tick(epoch) {
    if (epoch !== generation || !active()) return;
    if (performance.now() - captureStartedAt >= 7190000) {
      await lost('camera_time_limit');
      message.textContent = 'Camera reached its two-hour session limit. Restart a permitted assessment after review.';
      return;
    }
    if (document.hidden) {
      visibilityGap = true;
      showQualityStatus();
      message.textContent = 'Camera session retained; hidden-tab frames are not measured. Return to the assessment.';
      timer = setTimeout(() => tick(epoch), 1000);
      return;
    }
    try {
      const c = identity();
      if (JSON.stringify(c) !== JSON.stringify(segment)) await finishSegment();
      if (video.readyState >= 2 && video.currentTime !== lastFrame) {
        lastFrame = video.currentTime;
        const result = model.detectForVideo(video, performance.now());
        const landmarks = result.faceLandmarks || [];
        const faces = landmarks.length;
        observedFrames += 1;
        if (faces === 1) observedSingleFaceFrames += 1;
        showQualityStatus();
        if (ctx) {
          ctx.clearRect(0, 0, 320, 240);
          ctx.fillStyle = '#176557';
          for (const face of landmarks) for (const p of face) {
            ctx.beginPath(); ctx.arc(p.x * 320, p.y * 240, 1, 0, Math.PI * 2); ctx.fill();
          }
        }
        const sample = { at_ms: performance.now() - began, faces: Math.min(faces, 2) };
        if (faces === 1) {
          const lm = landmarks[0];
          const blend = Object.fromEntries((result.faceBlendshapes?.[0]?.categories || []).map(x => [x.categoryName, x.score]));
          const xs = lm.map(p => p.x);
          const ys = lm.map(p => p.y);
          sample.center_x = (Math.max(...xs) + Math.min(...xs)) / 2;
          sample.center_y = (Math.max(...ys) + Math.min(...ys)) / 2;
          sample.face_width = Math.max(...xs) - Math.min(...xs);
          sample.blink_left = blend.eyeBlinkLeft ?? null;
          sample.blink_right = blend.eyeBlinkRight ?? null;
          sample.jaw_open = blend.jawOpen ?? null;
          const distance = (a,b) => Math.hypot(a.x-b.x, a.y-b.y);
          sample.eye_open_ratio = distance(lm[159], lm[145]) / Math.max(distance(lm[33], lm[133]), .0001);
        }
        if (persist.checked && segment && rows.length < 7201) {
          rows.push(sample);
          showSaveStatus();
          // Send bounded batches while capture is active, instead of waiting
          // until a task switch or Stop; preserve each batch UUID for retry.
          if (rows.length >= 20) void finishSegment();
        }
        message.textContent = 'Camera live · ' + faces + ' face(s) · ' +
          (visibilityGap ? 'a hidden-tab gap was observed · ' : '') +
          (persist.checked ? 'derived samples queued' : 'local analysis only') +
          ' · not a clinical interpretation';
      }
    } catch (error) {
      await lost('camera_processing_error');
      message.textContent = 'Camera processing stopped: ' + error.message;
      return;
    }
    if (epoch === generation) timer = setTimeout(() => tick(epoch), 1000);
  }
  function cameraFailureGuidance(error) {
    const name = String(error?.name || '');
    const message = String(error?.message || error || 'Unknown camera error');
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
      return 'Camera access denied by browser or Windows. Allow Camera for this localhost site in Chrome settings and enable Windows camera permissions, then retry.';
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      return 'No accessible webcam was found. Connect or enable a camera, then retry.';
    }
    if (name === 'NotReadableError' || name === 'TrackStartError') {
      return 'The webcam could not be opened. Close other apps using the camera and retry.';
    }
    if (name === 'OverconstrainedError') {
      return 'The webcam cannot meet the requested video settings. Check its availability and configuration.';
    }
    if (/dynamically imported module|vision_bundle|face_landmarker\.task|failed to fetch/i.test(message)) {
      return 'The local face-tracking model could not load. Verify the /nc-vendor assets and BAINP static server, then retry.';
    }
    return message;
  }
  async function ensureActive() {
    if (active()) return true;
    if (starting) return starting;
    if (!consent.checked) {
      message.textContent = 'Explicit camera processing consent is required for this camera-enabled pathway.';
      throw Error('camera_consent_required');
    }
    const participant = identity();
    if (!participant) throw Error('Select a participant before starting the camera.');
    if (!navigator.mediaDevices?.getUserMedia) throw Error('Camera API unavailable. Use a supported browser on localhost or HTTPS.');
    const epoch = ++generation;
    starting = (async () => {
      startButton.disabled = true;
      try {
        const permissions = await request(participant, '/permissions');
        if (persist.checked && !permissions.camera) {
          showStorageGuidance();
          throw Error('camera_storage_authorization_required');
        }
        revision = permissions.revision;
        message.textContent = 'Loading local face-landmark model…';
        const { FilesetResolver, FaceLandmarker } = await import('/nc-vendor/vision_bundle.mjs');
        const files = await FilesetResolver.forVisionTasks('/nc-vendor');
        model ??= await FaceLandmarker.createFromOptions(files, {
          baseOptions: { modelAssetPath: '/nc-vendor/face_landmarker.task', delegate: 'CPU' },
          runningMode: 'VIDEO', numFaces: 2, outputFaceBlendshapes: true,
          minFaceDetectionConfidence: .5, minFacePresenceConfidence: .5,
          minTrackingConfidence: .5,
        });
        if (epoch !== generation || !consent.checked) throw Error('Camera start cancelled.');
        // User consent and the browser permission dialog remain authoritative.
        const acquired = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }, audio: false,
        });
        if (epoch !== generation || !consent.checked || document.hidden) {
          acquired.getTracks().forEach(t => t.stop());
          throw Error('Return to the visible assessment page and restart camera.');
        }
        stream = acquired;
        intentionalStop = false;
        const track = acquired.getVideoTracks()[0];
        track?.addEventListener('ended', () => {
          if (!intentionalStop && epoch === generation) void lost('camera_device_disconnected');
        });
        video.srcObject = acquired;
        await video.play();
        if (!active()) throw Error('Camera stream ended before the assessment could start.');
        captureStartedAt = performance.now();
        began = captureStartedAt;
        segment = identity();
        rows = [];
        observedFrames = 0;
        observedSingleFaceFrames = 0;
        visibilityGap = false;
        lastFrame = -1;
        showSaveStatus();
        showQualityStatus();
        void tick(epoch);
        poll = setInterval(async () => {
          try {
            const state = await request(participant, '/permissions');
            if (persist.checked && (!state.camera || state.revision !== revision)) {
              rows = []; pending = []; persist.checked = false;
              showSaveStatus();
              message.textContent = 'Storage permission changed. Local camera analysis continues; no samples will be saved.';
            }
          } catch {
            // Network failures must not silently revoke independently consented local processing.
            if (persist.checked) message.textContent = 'Camera live; storage-permission check unavailable. Avoid relying on sample persistence.';
          }
        }, 5000);
        return true;
      } catch (error) {
        if (epoch === generation) await stop({ notify: false, clearUnsent: true });
        if (error.message === 'camera_storage_authorization_required') showStorageGuidance();
        else message.textContent = 'Camera unavailable: ' + cameraFailureGuidance(error);
        throw error;
      } finally {
        starting = null;
        startButton.disabled = false;
      }
    })();
    return starting;
  }
  grantButton.onclick = () => void authorizeStorage().catch(() => {});
  startButton.onclick = () => void ensureActive().catch(() => {});
  stopButton.onclick = () => void stop({ reason: 'camera_user_stopped' });
  retryButton.onclick = () => void finishSegment();
  consent.onchange = () => {
    if (!consent.checked) void stop({ reason: 'camera_consent_withdrawn', clearUnsent: true });
    else message.textContent = 'Live processing consent recorded locally. Start the camera, or authorize sample storage first if you selected saving.';
  };
  persist.onchange = () => {
    if (active()) {
      rows = []; pending = []; persist.checked = false;
      showSaveStatus();
      message.textContent = 'Stop and restart capture to change derived-data storage settings.';
    } else if (persist.checked) {
      showStorageGuidance();
      showSaveStatus();
    } else {
      showSaveStatus();
      message.textContent = 'Local camera processing selected. Derived measurements will not be saved to your account.';
    }
  };
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      visibilityGap = true;
      // DO NOT stop on screenshot overlays or hidden tabs. Browser may suspend frames.
    } else if (active()) {
      void video.play().catch(() => { message.textContent = 'Camera video could not resume; review permissions.'; });
    }
  });
  window.addEventListener('pagehide', discard);
  showSaveStatus();
  showQualityStatus();
  return {
    active, ensureActive, authorizeStorage, finishSegment, pendingCount: () => pending.length,
    taskChanged: finishSegment, stop,
    showSetup: () => { panel.open = true; panel.scrollIntoView?.({ block: 'start' }); },
  };
}
