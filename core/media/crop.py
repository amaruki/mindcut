import os
import subprocess
import multiprocessing
import json
import numpy as np
from .. import config


# ---------------------------------------------------------------------------
# GPU / backend detection
# ---------------------------------------------------------------------------

def _detect_cv2_backend():
    try:
        import cv2

        if cv2.cuda.getCudaEnabledDeviceCount() > 0:
            return "cuda"
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)
            if cv2.ocl.useOpenCL():
                return "opencl"
    except Exception:
        pass
    return "cpu"

_BACKEND = None

def _backend():
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = _detect_cv2_backend()
    return _BACKEND

def _to_gpu(mat):
    import cv2

    b = _backend()
    if b == "cuda":
        g = cv2.cuda_GpuMat()
        g.upload(mat)
        return g
    if b == "opencl":
        return cv2.UMat(mat)
    return mat

def _to_cpu(mat):
    b = _backend()
    if b == "cuda":
        return mat.download()
    if b == "opencl":
        return mat.get()
    return mat

def _gpu_resize(src, size):
    import cv2

    if _backend() == "cuda":
        return cv2.cuda.resize(src, size, interpolation=cv2.INTER_LINEAR)
    return cv2.resize(src, size, interpolation=cv2.INTER_LINEAR)


# ---------------------------------------------------------------------------
# ffprobe
# ---------------------------------------------------------------------------

def _probe_video(path):
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,nb_frames",
            "-of",
            "json",
            path,
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        info = json.loads(out)["streams"][0]
        w = int(info["width"])
        h = int(info["height"])
        num, den = info["r_frame_rate"].split("/")
        fps = float(num) / max(float(den), 1)
        total = int(info.get("nb_frames") or 0)
        return w, h, fps, total
    except Exception:
        return None


# ---------------------------------------------------------------------------
# FFmpeg hardware decoder
# ---------------------------------------------------------------------------

_HW_DECODE_OPTIONS = [
    ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"],
    ["-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi"],
    ["-hwaccel", "qsv"],
    ["-hwaccel", "videotoolbox"],
    ["-hwaccel", "d3d11va"],
    ["-hwaccel", "dxva2"],
]
_DECODE_CMD_CACHE = {}


def _build_ffmpeg_decode_cmd(in_path, in_w, in_h, vf_prefix=None):
    if in_path in _DECODE_CMD_CACHE and not vf_prefix:
        return _DECODE_CMD_CACHE[in_path]
    frame_bytes = in_w * in_h * 3
    for hw_opts in _HW_DECODE_OPTIONS:
        needs_hw = "output_format" in " ".join(hw_opts)
        vf_base = "hwdownload,format=bgr24" if needs_hw else "format=bgr24"
        vf = f"{vf_prefix},{vf_base}" if vf_prefix else vf_base
        cmd = (
            ["ffmpeg", "-loglevel", "error"]
            + hw_opts
            + [
                "-i",
                in_path,
                "-f",
                "rawvideo",
                "-pix_fmt",
                "bgr24",
                "-vf",
                vf,
                "pipe:1",
            ]
        )
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            chunk = p.stdout.read(frame_bytes)
            p.kill()
            p.wait()
            if len(chunk) == frame_bytes:
                _DECODE_CMD_CACHE[in_path] = cmd
                return cmd
        except Exception:
            pass
    vf_base = "format=bgr24"
    vf = f"{vf_prefix},{vf_base}" if vf_prefix else vf_base
    cmd = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        in_path,
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-vf",
        vf,
        "pipe:1",
    ]
    if not vf_prefix:
        _DECODE_CMD_CACHE[in_path] = cmd
    return cmd


# ---------------------------------------------------------------------------
# FFmpeg hardware encoder
# ---------------------------------------------------------------------------

# (encoder_name, extra_args)
_HW_ENCODE_OPTIONS = [
    ("h264_nvenc", ["-preset", "p4", "-rc", "vbr", "-cq", "23"]),
    ("h264_videotoolbox", ["-q:v", "65"]),
    ("h264_vaapi", ["-vf", "format=nv12,hwupload", "-qp", "23"]),
    ("h264_qsv", ["-preset", "medium"]),
    ("h264_amf", ["-quality", "balanced"]),
    ("libx264", ["-preset", "veryfast", "-crf", "23"]),
]
_ENCODE_CMD_CACHE = {}

def _build_ffmpeg_encode_cmd(out_path, out_w, out_h, fps):
    key = (out_path, out_w, out_h, fps)
    if key in _ENCODE_CMD_CACHE:
        return _ENCODE_CMD_CACHE[key]
    dummy = bytes(out_w * out_h * 3)
    for enc, extra in _HW_ENCODE_OPTIONS:
        cmd = (
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "bgr24",
                "-s",
                f"{out_w}x{out_h}",
                "-r",
                str(fps),
                "-i",
                "pipe:0",
                "-vf",
                "format=yuv420p",
                "-c:v",
                enc,
            ]
            + extra
            + [out_path]
        )
        try:
            p = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            p.stdin.write(dummy)
            p.stdin.close()
            p.wait(timeout=5)
            if p.returncode == 0:
                _ENCODE_CMD_CACHE[key] = cmd
                return cmd
        except Exception:
            pass
    raise RuntimeError("No working FFmpeg encoder found.")


# ---------------------------------------------------------------------------
# Face detection
# ---------------------------------------------------------------------------

_DNN_NET = None
_DNN_TRIED = False
DETECT_THUMB_W = 320  # downscale to this width before detection (~16x fewer pixels)


def _get_dnn_detector():
    global _DNN_NET, _DNN_TRIED
    if _DNN_TRIED:
        return _DNN_NET
    _DNN_TRIED = True
    try:
        import cv2

        model_dir = os.path.join(os.path.dirname(__file__), "models")
        proto = os.path.join(model_dir, "deploy.prototxt")
        model = os.path.join(model_dir, "res10_300x300_ssd_iter_140000.caffemodel")
        if not (os.path.exists(proto) and os.path.exists(model)):
            return None
        net = cv2.dnn.readNetFromCaffe(proto, model)
        b = _backend()
        if b == "cuda":
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
        elif b == "opencl":
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_OPENCL)
        else:
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        _DNN_NET = net
    except Exception:
        pass
    return _DNN_NET

def _load_haar_cascade():
    import cv2

    path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    c = cv2.CascadeClassifier(path)
    return None if c.empty() else c

def _detect_faces_on_thumbnail(thumb_bgr, cascade, orig_w, orig_h):
    import cv2

    th, tw = thumb_bgr.shape[:2]
    sx, sy = orig_w / tw, orig_h / th
    net = _get_dnn_detector()
    if net is not None:
        blob = cv2.dnn.blobFromImage(
            cv2.resize(thumb_bgr, (300, 300)),
            1.0,
            (300, 300),
            (104.0, 177.0, 123.0),
            swapRB=False,
        )
        net.setInput(blob)
        dets = net.forward()
        faces = []
        for i in range(dets.shape[2]):
            if float(dets[0, 0, i, 2]) < 0.5:
                continue
            x1 = dets[0, 0, i, 3] * tw
            y1 = dets[0, 0, i, 4] * th
            x2 = dets[0, 0, i, 5] * tw
            y2 = dets[0, 0, i, 6] * th
            cx, cy = (x1 + x2) / 2 * sx, (y1 + y2) / 2 * sy
            area = (x2 - x1) * (y2 - y1)
            faces.append(((cx, cy), area))
        if faces:
            faces.sort(key=lambda f: f[1], reverse=True)
            return [f[0] for f in faces]

    gray = cv2.cvtColor(thumb_bgr, cv2.COLOR_BGR2GRAY)
    faces_hc = cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=4, minSize=(20, 20)
    )
    if len(faces_hc) > 0:
        faces_hc = sorted(faces_hc, key=lambda f: f[2] * f[3], reverse=True)
        return [((x + w / 2) * sx, (y + h / 2) * sy) for x, y, w, h in faces_hc]
    return []


# ---------------------------------------------------------------------------
# Unchanged public helpers
# ---------------------------------------------------------------------------


def build_cover_scale_crop_vf(out_w, out_h):
    ar_expr = f"{out_w}/{out_h}"
    scale = (
        f"scale='if(gte(iw/ih,{ar_expr}),-2,{out_w})'"
        f":'if(gte(iw/ih,{ar_expr}),{out_h},-2)'"
    )
    crop = f"crop={out_w}:{out_h}:(iw-{out_w})/2:(ih-{out_h})/2"
    return f"{scale},{crop}"


def build_cover_scale_vf(out_w, out_h):
    ar_expr = f"{out_w}/{out_h}"
    return (
        f"scale='if(gte(iw/ih,{ar_expr}),-2,{out_w})'"
        f":'if(gte(iw/ih,{ar_expr}),{out_h},-2)'"
    )


def get_split_heights(out_h):
    if not out_h:
        return None, None
    bottom = min(config.BOTTOM_HEIGHT, max(1, out_h - 1))
    top = max(1, out_h - bottom)
    return top, bottom


def clamp_int(value, min_value, max_value):
    return int(max(min_value, min(max_value, int(value))))


# ---------------------------------------------------------------------------
# SpeakerTracker
#
# Solves three root causes of a shaky output:
#
#   Problem 1 – Multiple faces in frame
#     After a warm-up phase the tracker locks onto a *speaker anchor*
#     (median position of the first `warmup_detections` positive hits).
#     Only the face closest to that anchor AND within
#     `lock_radius_frac * in_w` pixels is accepted as the speaker.
#     All other faces (bystanders) are silently ignored.
#
#   Problem 2 – Missing / flickering detections
#     When no face passes the radius test the target position is held
#     unchanged.  The EMA still runs every frame so the crop window
#     continues gliding smoothly — no sudden snap or jump.
#     After `max_no_detect` consecutive missed frames the lock radius
#     doubles temporarily to allow recovery from occlusion.
#
#   Problem 3 – Micro-jitter from detection noise
#     A dead-zone (`dead_zone_frac * in_w`) prevents the target from
#     updating unless the speaker has moved meaningfully.  Combined with a
#     low EMA alpha (default 0.04, vs the old 0.1) the crop window barely
#     reacts to single-frame detection noise.
#
#   Bonus: speaker who walks across the frame
#     The anchor drifts toward the confirmed speaker at `anchor_drift`
#     per frame, so the tracker follows gradual movement without ever
#     losing its identity lock.
# ---------------------------------------------------------------------------


class SpeakerTracker:
    """
    Stable, speaker-identity-aware crop tracker.

    Usage (inside a per-frame loop)::

        tracker = SpeakerTracker(in_w, in_h)
        ...
        tracker.update(face_hits)   # face_hits = [(cx,cy), ...] or []
        crop_x = clamp_int(tracker.smooth_x - crop_w / 2, 0, in_w - crop_w)
        crop_y = clamp_int(tracker.smooth_y - crop_h / 2, 0, in_h - crop_h)
    """

    def __init__(
        self,
        in_w: int,
        in_h: int,
        *,
        warmup_detections: int = 20,  # positive hits before locking
        ema_alpha: float = 0.04,  # smoothing strength (lower = smoother)
        dead_zone_frac: float = 0.018,  # ignore motion < this fraction of width
        lock_radius_frac: float = 0.35,  # bystander exclusion radius (fraction of width)
        anchor_drift: float = 0.015,  # how fast anchor follows confirmed speaker
        max_no_detect: int = 90,  # frames before widening lock radius
    ):
        self.in_w = in_w
        self.in_h = in_h
        self._alpha = ema_alpha
        self._dead_zone_sq = (in_w * dead_zone_frac) ** 2
        self._lock_radius_sq = (in_w * lock_radius_frac) ** 2
        self._anchor_drift = anchor_drift
        self._warmup_needed = warmup_detections
        self._max_no_detect = max_no_detect

        # Initialise everything to the frame centre
        cx0, cy0 = float(in_w) / 2, float(in_h) / 2
        self.smooth_x = cx0  # ← read this for crop centre X
        self.smooth_y = cy0  # ← read this for crop centre Y
        self._target_x = cx0
        self._target_y = cy0
        self._anchor_x = cx0
        self._anchor_y = cy0

        self._locked = False
        self._warmup = []  # (cx, cy) samples during warm-up
        self._no_detect_streak = 0  # consecutive frames with no valid face

    # ------------------------------------------------------------------
    def update(self, face_hits: list) -> None:
        """
        Call once per frame (or once per detection cycle with [] on
        non-detection frames).

        Parameters
        ----------
        face_hits : list of (cx, cy)
            Detected face centres in *original* pixel coords, sorted by
            face area descending (largest / most prominent face first).
            Pass an empty list when no detection was run or no face found.
        """
        chosen = self._pick_speaker(face_hits)

        if chosen is not None:
            self._no_detect_streak = 0

            if not self._locked:
                # Warm-up phase: accumulate samples until we have enough
                # to compute a reliable median anchor.
                self._warmup.append(chosen)
                if len(self._warmup) >= self._warmup_needed:
                    self._establish_anchor()
            else:
                # Locked phase ──────────────────────────────────────────
                # 1. Drift anchor slowly toward the confirmed speaker so
                #    we can follow gradual movement across the frame.
                self._anchor_x += self._anchor_drift * (chosen[0] - self._anchor_x)
                self._anchor_y += self._anchor_drift * (chosen[1] - self._anchor_y)

                # 2. Dead-zone: only update the target when the face has
                #    moved beyond the noise threshold.
                dx = chosen[0] - self._target_x
                dy = chosen[1] - self._target_y
                if dx * dx + dy * dy > self._dead_zone_sq:
                    self._target_x = chosen[0]
                    self._target_y = chosen[1]
        else:
            # No valid speaker face detected this frame.
            # Target is held; EMA will keep the crop gliding toward it.
            self._no_detect_streak += 1

        # EMA advances every frame regardless of detection result,
        # producing fluid motion between (sparse) detection cycles.
        self.smooth_x += self._alpha * (self._target_x - self.smooth_x)
        self.smooth_y += self._alpha * (self._target_y - self.smooth_y)

    # ------------------------------------------------------------------
    def _pick_speaker(self, hits: list):
        """
        Return (cx, cy) of the speaker face, or None.

        Before lock  → face closest to frame centre (ignores bystanders
                        that may be larger but off to the side).
        After lock   → face closest to anchor within the lock radius.
                        Faces outside the radius are bystanders → None.
                        After a long no-detect streak the radius doubles
                        to allow recovery from occlusion / re-entry.
        """
        if not hits:
            return None

        if not self._locked:
            cx0, cy0 = float(self.in_w) / 2, float(self.in_h) / 2
            return min(hits, key=lambda p: (p[0] - cx0) ** 2 + (p[1] - cy0) ** 2)

        # Locked: enforce identity via proximity to anchor
        r_sq = self._lock_radius_sq
        if self._no_detect_streak > self._max_no_detect:
            r_sq *= 4.0  # temporary wider search after long absence

        ref_x, ref_y = self._anchor_x, self._anchor_y
        best, best_d = None, float("inf")
        for cx, cy in hits:
            d = (cx - ref_x) ** 2 + (cy - ref_y) ** 2
            if d < best_d and d < r_sq:
                best_d, best = d, (cx, cy)
        return best  # None → all detected faces are bystanders

    # ------------------------------------------------------------------
    def _establish_anchor(self) -> None:
        """Compute the median anchor from warm-up samples and lock."""
        xs = sorted(p[0] for p in self._warmup)
        ys = sorted(p[1] for p in self._warmup)
        self._anchor_x = xs[len(xs) // 2]
        self._anchor_y = ys[len(ys) // 2]
        # Snap smooth + target to anchor so the first locked frame
        # does not cause a visible lurch.
        self.smooth_x = self._anchor_x
        self.smooth_y = self._anchor_y
        self._target_x = self._anchor_x
        self._target_y = self._anchor_y
        self._locked = True
        self._warmup = []  # free memory


# ---------------------------------------------------------------------------
# detect_face_center  (static crop helper — unchanged public contract)
# ---------------------------------------------------------------------------


def detect_face_center(video_path, max_samples=12):
    try:
        import cv2  # noqa: F401
    except ImportError:
        return None
    cascade = _load_haar_cascade()
    if cascade is None:
        return None
    probe = _probe_video(video_path)
    if probe is None:
        return None
    in_w, in_h, fps, total = probe
    thumb_h = max(1, in_h * DETECT_THUMB_W // in_w)
    step_sec = max(1.0, (total / max(fps, 1)) / max_samples) if total else 2.0
    cmd = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        video_path,
        "-vf",
        f"fps=1/{step_sec:.2f},scale={DETECT_THUMB_W}:{thumb_h}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "pipe:1",
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        frame_bytes = DETECT_THUMB_W * thumb_h * 3
        centers = []
        while len(centers) < max_samples:
            raw = proc.stdout.read(frame_bytes)
            if len(raw) < frame_bytes:
                break
            thumb = np.frombuffer(raw, dtype=np.uint8).reshape(
                thumb_h, DETECT_THUMB_W, 3
            )
            centers.extend(_detect_faces_on_thumbnail(thumb, cascade, in_w, in_h))
        proc.kill()
        proc.wait()
    except Exception:
        return None
    if not centers:
        return None
    xs = sorted(c[0] for c in centers)
    ys = sorted(c[1] for c in centers)
    return xs[len(xs) // 2], ys[len(ys) // 2], in_w, in_h


# ---------------------------------------------------------------------------
# build_face_crop_vf
# ---------------------------------------------------------------------------


def build_face_crop_vf(video_path, out_w, out_h):
    if not out_w or not out_h:
        return None
    face = detect_face_center(video_path)
    if not face:
        return None
    cx, cy, in_w, in_h = face
    if in_w <= 0 or in_h <= 0:
        return None
    ratio = out_w / out_h
    crop_w = min(in_w, int(in_h * ratio))
    crop_h = int(crop_w / ratio)
    if crop_w <= 0 or crop_h <= 0:
        return None
    x = clamp_int(cx - crop_w / 2, 0, in_w - crop_w)
    y = clamp_int(cy - crop_h / 2, 0, in_h - crop_h)
    return f"crop={crop_w}:{crop_h}:{x}:{y},scale={out_w}:{out_h}"


# ---------------------------------------------------------------------------
# Processor — dedicated OS process, fully escapes the Python GIL
#
# Key changes vs. the original implementation:
#   • SpeakerTracker replaces the ad-hoc last_cx/next_cx interpolation.
#     There is now a single, well-defined smoothing layer (EMA inside the
#     tracker) instead of two competing layers.
#   • tracker.update([]) is called on every non-detection frame so the EMA
#     advances continuously for silky motion even between detect cycles.
#   • Bystander rejection and dead-zone logic live entirely in the tracker;
#     the worker loop stays simple and readable.
# ---------------------------------------------------------------------------


def _processor_worker(in_w, in_h, out_w, out_h, read_q, write_q, detect_every, error_q):
    try:
        import cv2

        cascade = _load_haar_cascade()
        thumb_h = max(1, in_h * DETECT_THUMB_W // in_w)
        ratio = out_w / out_h
        crop_w = min(in_w, int(in_h * ratio))
        crop_h = int(crop_w / ratio)

        tracker = SpeakerTracker(in_w, in_h)
        frame_idx = 0

        while True:
            item = read_q.get()
            if item is None:
                break

            frame = np.frombuffer(item, dtype=np.uint8).reshape(in_h, in_w, 3)

            # ── Sparse detection on a down-scaled thumbnail ─────────────────
            if frame_idx % detect_every == 0:
                thumb = cv2.resize(
                    frame, (DETECT_THUMB_W, thumb_h), interpolation=cv2.INTER_AREA
                )
                hits = _detect_faces_on_thumbnail(thumb, cascade, in_w, in_h)
                tracker.update(hits)
            else:
                # No detection this frame — EMA still advances toward target,
                # keeping the crop window moving smoothly.
                tracker.update([])

            # ── Stable crop window driven by a single smoothed position ─────
            crop_x = clamp_int(tracker.smooth_x - crop_w / 2, 0, in_w - crop_w)
            crop_y = clamp_int(tracker.smooth_y - crop_h / 2, 0, in_h - crop_h)

            cropped = frame[crop_y : crop_y + crop_h, crop_x : crop_x + crop_w]
            out_frame = _to_cpu(_gpu_resize(_to_gpu(cropped), (out_w, out_h)))
            write_q.put(out_frame.tobytes())
            frame_idx += 1

    except Exception as e:
        error_q.put(str(e))
    finally:
        write_q.put(None)


# ---------------------------------------------------------------------------
# dynamic_face_crop_video
#
#   [FFmpeg HW decode] ─raw bytes─▶ [OS Process: detect + GPU resize]
#                                  ─raw bytes─▶ [FFmpeg HW encode]
#
#  Decode:   NVDEC / VAAPI / VideoToolbox / QSV / D3D11VA  (or SW fallback)
#  Process:  true OS subprocess — no GIL, GPU resize, thumbnail-only detect
#  Encode:   NVENC / VideoToolbox / VAAPI / QSV / AMF       (or libx264 SW)
# ---------------------------------------------------------------------------

_DETECT_EVERY = 8
_QUEUE_DEPTH = 48


def dynamic_face_crop_video(
    in_path, out_path, out_w, out_h, detect_every=_DETECT_EVERY, vf=None
):
    probe = _probe_video(in_path)
    if probe is None:
        return False
    in_w, in_h, fps, _ = probe
    if in_w <= 0 or in_h <= 0 or not out_w or not out_h:
        return False

    frame_in_bytes = in_w * in_h * 3
    decode_cmd = _build_ffmpeg_decode_cmd(in_path, in_w, in_h, vf_prefix=vf)
    try:
        encode_cmd = _build_ffmpeg_encode_cmd(out_path, out_w, out_h, fps)
    except RuntimeError as e:
        print(f"[dynamic_face_crop_video] encoder error: {e}")
        return False

    print(f"[dynamic_face_crop_video] cv2 GPU backend : {_backend()}")
    print(f"[dynamic_face_crop_video] decoder         : {decode_cmd}")
    print(f"[dynamic_face_crop_video] encoder         : {encode_cmd}")

    ctx = multiprocessing.get_context("spawn")
    read_q = ctx.Queue(maxsize=_QUEUE_DEPTH)
    write_q = ctx.Queue(maxsize=_QUEUE_DEPTH)
    error_q = ctx.Queue()

    proc_worker = ctx.Process(
        target=_processor_worker,
        args=(in_w, in_h, out_w, out_h, read_q, write_q, detect_every, error_q),
        daemon=True,
    )
    proc_worker.start()

    encoder = subprocess.Popen(
        encode_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    import threading

    def writer():
        try:
            while True:
                item = write_q.get()
                if item is None:
                    break
                encoder.stdin.write(item)
            encoder.stdin.close()
        except Exception:
            try:
                encoder.stdin.close()
            except Exception:
                pass

    writer_thread = threading.Thread(target=writer, daemon=True)
    writer_thread.start()

    # Main thread: pump decoded frames into the processing queue
    decoder = subprocess.Popen(
        decode_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    try:
        while True:
            raw = decoder.stdout.read(frame_in_bytes)
            if len(raw) < frame_in_bytes:
                break
            read_q.put(raw)
    finally:
        decoder.stdout.close()
        decoder.wait()
        read_q.put(None)  # signal processor to finish

    proc_worker.join()
    writer_thread.join()
    encoder.wait()

    if not error_q.empty():
        print(f"[dynamic_face_crop_video] processor error: {error_q.get()}")
        return False
    return True
