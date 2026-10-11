"""Ordered inference, observed-only scoring, interpolation and single-pass export."""
from collections import deque
from dataclasses import asdict
import json
import subprocess
import time
import traceback
import cv2
import numpy as np
from .config import DATA
from .models import ModelBundle
from .video import VideoSource, ActivityGate
from .court import Court, PlayerCourtGuide
from .tracking import TrackingEngine, AnalyticsEngine
from .rally import ContactDetector, RallyMachine, RallyState
from .interpolation import interpolate_tracks
from .sports import score_session, SPORTS
from .storage import get, save, transition

DEFAULT_OPTIONS = {'frame_stride':3, 'inference_size':640, 'max_width':1280,
                   'device':'cuda', 'auto_score':False, 'score_threshold':.75}


class VideoEncoder:
    """Encode annotated H.264 once, instead of MP4V followed by transcoding."""
    def __init__(self, folder, fps, shape):
        import imageio_ffmpeg
        self.log = (folder / 'encoder.log').open('wb')
        height, width = shape[:2]
        self.process = subprocess.Popen([
            imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error',
            '-f', 'rawvideo', '-vcodec', 'rawvideo', '-pix_fmt', 'bgr24',
            '-s', f'{width}x{height}', '-r', str(fps), '-i', '-', '-an',
            '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264',
            '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart', str(folder / 'annotated.mp4')],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.log)

    def write(self, image):
        self.process.stdin.write(image.tobytes())

    def close(self):
        try:
            self.process.stdin.close()
            if self.process.wait(timeout=120) != 0:
                raise RuntimeError('Annotated video encoding failed; see encoder.log.')
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            raise RuntimeError('Video encoder did not finish in time.')
        finally:
            self.log.close()


def render(frame, players, ball, trail, court, activity, rally_state, score, interpolated=False):
    image = frame.image.copy()
    if court:
        points = (np.array(court.corners) * [image.shape[1], image.shape[0]]).astype(np.int32)
        cv2.polylines(image, [points], True, (120, 220, 190), 2)
    for key, player in players.items():
        x1, y1, x2, y2 = map(int, player['box'])
        color = (120, 240, 190) if key == 'A' else (255, 170, 110)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        label = f'Player {key}'
        cv2.putText(image, label, (x1, max(y1-8, 20)), cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1)
        for point in player['keypoints']:
            if len(point) >= 3 and point[2] > .4:
                cv2.circle(image, (int(point[0]), int(point[1])), 2, color, -1)
    if len(trail) > 1:
        cv2.polylines(image, [np.array([item['point'] for item in trail], np.int32)], False, (90, 230, 245), 1)
    if ball:
        x1,y1,x2,y2 = map(int, ball.box)
        cv2.rectangle(image, (x1-3,y1-3), (x2+3,y2+3), (90,230,245), 2)
    cv2.rectangle(image, (0,0), (min(image.shape[1],660),62), (20,30,25), -1)
    match_state = {'IN_RALLY':'Rally in progress','WAITING_FOR_SERVE':'Preparing to serve',
                   'RALLY_ENDED':'Rally complete','UPDATE_SCORE':'Preparing next rally'}.get(rally_state,'Match review')
    cv2.putText(image, match_state, (12,23), cv2.FONT_HERSHEY_SIMPLEX, .55, (220,245,190), 1)
    cv2.putText(image, f'{frame.time:.2f}s | Movement and rally review',
                (12,47), cv2.FONT_HERSHEY_SIMPLEX, .45, (240,240,240), 1)
    return image


def run_session(session_id):
    session = get(session_id)
    if not session or session['status'] not in ('queued', 'failed'):
        return
    output = DATA / 'sessions' / session_id
    output.mkdir(parents=True, exist_ok=True)
    stop_file = output / 'stop'
    encoder = source = None
    try:
        session.update(status='loading', error=None)
        if not transition(session, ['queued','failed']):
            return
        options = {**DEFAULT_OPTIONS, **session.get('options',{})}
        stride = options['frame_stride']
        started = time.perf_counter()
        bundle = ModelBundle(session['sport'], session['pose'], options['device'], options['inference_size'])
        source = VideoSource(session['source'], live=session['live'],
                             chunk_seconds=2.0 if session['live'] else 10.0,
                             overlap_seconds=.5 if session['live'] else 1.0,
                             max_width=options['max_width'])
        analytics, gate = AnalyticsEngine(sport=session['sport']), ActivityGate()
        detector = ContactDetector(session['sport'])
        auto_score = False
        machine = RallyMachine(session['sport'], auto_score, options['score_threshold'])
        court = tracker = None
        player_guide = PlayerCourtGuide(session['sport'])
        pending, between = deque(), []
        previous = None
        latest_read = -1
        latest_activity = -10.0
        processed = inferred = 0
        saved_at = time.perf_counter()
        last_image = None
        preview_files = deque(maxlen=3)
        session.update(status='processing', events=[], score=score_session({'sport':session['sport'],'events':[]}),
                       options=options, runtime=bundle.runtime)
        save(session)

        def publish():
            nonlocal saved_at
            if last_image is not None:
                path = output / f'preview-{processed}.jpg'
                cv2.imwrite(str(path), last_image)
                if path not in preview_files:
                    if len(preview_files) == preview_files.maxlen:
                        old = preview_files.popleft()
                        try:
                            old.unlink(missing_ok=True)
                        except PermissionError:
                            pass
                    preview_files.append(path)
                session['preview'] = f'/api/sessions/{session_id}/media/{path.name}'
            session.update(analytics=analytics.snapshot(session.get('source_seconds',0)),
                           processing_fps=round(processed/max(time.perf_counter()-started,.001),2),
                           filtered_percent=round(100*(1-inferred/max(processed,1)),1))
            save(session)
            saved_at = time.perf_counter()

        with (output/'frames.jsonl').open('w', encoding='utf-8') as records:
            def write_frame(item, players, ball, events, context, interpolated=False):
                nonlocal encoder, processed, last_image
                frame, active, activity = item
                last_image = render(frame, players, ball, context['trail'], court, activity,
                                    context['state'], context['score'], interpolated)
                if encoder is None:
                    encoder = VideoEncoder(output, source.fps, last_image.shape)
                encoder.write(last_image)
                records.write(json.dumps({'frame':frame.index, 'time':frame.time, 'active':active,
                    'inferred':not interpolated and context.get('inferred',False), 'interpolated':interpolated,
                    'players':players, 'ball':list(ball.center) if ball else None,
                    'events':[asdict(event) for event in events], 'rally_state':context['state'],
                    'score':context['score']['points']})+'\n')
                processed += 1
                session.update(processed_frames=processed, inferred_frames=inferred,
                               source_seconds=round(frame.time,3), total_frames=source.total_frames,
                               activity=activity, rally_state=machine.state.value, rally_reason=machine.reason)
                if time.perf_counter()-saved_at >= .8:
                    publish()

            def consume(item):
                nonlocal court, tracker, inferred, previous
                frame, initial_active, activity = item
                active = initial_active or 0 <= latest_activity-frame.time <= .5
                if court is None and session.get('corners'):
                    court = Court(session['sport'],session['corners'],frame.image.shape)
                if tracker is None:
                    tracker = TrackingEngine(use_bytetrack=True, inference_fps=source.fps/stride)

                # If broadcast cuts away during a rally, abandon rally cleanly without awarding points
                if activity == 'cutaway' and machine.state == RallyState.IN_RALLY:
                    machine.state = RallyState.WAITING_FOR_SERVE
                    machine.rules = SPORTS[session['sport']]()
                    machine.reason = 'Broadcast cutaway / play interrupted'

                run_inference = active and (frame.index % stride == 0 or previous is None)
                if active and not run_inference:
                    between.append((frame,active,activity))
                    return
                players, ball, events = {}, None, []
                player_court = court
                if run_inference:
                    # An unconfirmed outline only guides player selection. It
                    # must never supply physical distances or landing decisions.
                    player_court = court or player_guide.update(frame.image)
                    objects, people = bundle.infer(frame.image,court=player_court)
                    players, ball, _ = tracker.update(objects,people,frame.time,frame.image.shape,player_court)
                    if activity not in ('idle', 'cutaway'):
                        events = detector.update(ball,players,frame.time,court,frame.image.shape)
                        if ball:
                            machine.observe_ball(frame.time)
                    else:
                        detector.update(None,{},frame.time,court,frame.image.shape)
                        events = []
                    inferred += 1
                else:
                    detector.update(None,{},frame.time,court,frame.image.shape)
                decision = machine.step(events,frame.time)
                if decision:
                    if session['sport']=='badminton':
                        decision.winner, decision.status = None, 'observed'
                    session['events'].append({**asdict(decision),'kind':'rally end','automatic':decision.status=='confirmed'})
                    session['score'] = score_session(session)
                active_court = court or player_court
                analytics.update(players,events,frame.time,active_court,frame.image.shape,
                                 rally_state=machine.state.value,decision=decision,play_visible=activity!='cutaway',observation_sample=run_inference)
                session['object_speed_px_s'] = round(tracker.object_speed,1) if ball and tracker.object_speed is not None else None
                context = {'state':machine.state.value,'score':session['score'], 'trail':list(tracker.ball), 'inferred':run_inference}
                current = {'time':frame.time,'players':players,'ball':ball,'generation':tracker.ball_generation,'context':context}
                for skipped in between:
                    display_players,display_ball = interpolate_tracks(previous,current,skipped[0].time)
                    write_frame(skipped,display_players,display_ball,[],previous['context'] if previous else context,True)
                between.clear()
                write_frame((frame,active,activity),players,ball,events,context)
                previous = current if run_inference else None

            for chunk in source:
                if stop_file.exists():
                    source.stop.set()
                    break
                for frame in chunk.frames:
                    if frame.index <= latest_read:
                        continue
                    latest_read = frame.index
                    active, _ = gate.inspect(frame, session.get('corners'))
                    if gate.state in ('active play', 'ready'):
                        latest_activity = frame.time
                    pending.append((frame, active, gate.state))
                    while pending and frame.time-pending[0][0].time >= .5:
                        consume(pending.popleft())
                        if stop_file.exists():
                            break
                    if stop_file.exists():
                        break
            while pending and not stop_file.exists():
                consume(pending.popleft())
            decision = machine.step([],session.get('source_seconds',0))
            if decision:
                if session['sport']=='badminton':
                    decision.winner, decision.status = None, 'observed'
                session['events'].append({**asdict(decision),'kind':'rally end','automatic':decision.status=='confirmed'})
                session['score'] = score_session(session)
                analytics.update({},[],session.get('source_seconds',0),court,
                                 rally_state=machine.state.value,decision=decision,observation_sample=False)
            analytics.finalize(session.get('source_seconds',0))
            for skipped in between:
                write_frame(skipped,{},None,[],previous['context'],True)
        if processed == 0 and not stop_file.exists():
            raise ValueError('The source contained no decodable frames.')
        session['status'] = 'encoding'
        publish()
        if encoder:
            encoder.close()
            encoder = None
            session['video'] = f'/api/sessions/{session_id}/media/annotated.mp4'
        session.update(status='cancelled' if stop_file.exists() else 'completed',
                       records=f'/api/sessions/{session_id}/media/frames.jsonl',
                       elapsed_seconds=round(time.perf_counter()-started,3))
        publish()
    except Exception as exc:
        session.update(status='failed',error=str(exc))
        save(session)
        (output/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        if encoder:
            try:
                encoder.close()
            except Exception:
                pass
        if source:
            source.stop.set()
