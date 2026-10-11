"""Display-only interpolation between real observations of the same tracks."""
import numpy as np
from .models import Detection


def interpolate_tracks(previous, current, timestamp):
    if not previous or not current:
        return {}, None
    delta = current['time'] - previous['time']
    if not 0 < delta <= .35 or not previous['time'] <= timestamp <= current['time']:
        return {}, None
    fraction = (timestamp - previous['time']) / delta

    def blend(a, b):
        return (np.asarray(a)*(1-fraction) + np.asarray(b)*fraction).tolist()

    players = {}
    for key in previous['players'].keys() & current['players'].keys():
        a, b = previous['players'][key], current['players'][key]
        if a.get('track_id') != b.get('track_id'):
            continue
        points = blend(a['keypoints'], b['keypoints']) if np.shape(a['keypoints']) == np.shape(b['keypoints']) else []
        players[key] = {'box':blend(a['box'],b['box']), 'foot':blend(a['foot'],b['foot']),
                        'keypoints':points, 'time':timestamp, 'track_id':a.get('track_id'), 'interpolated':True}
    ball = None
    if previous['ball'] and current['ball'] and previous['generation'] == current['generation']:
        ball = Detection(blend(previous['ball'].box,current['ball'].box),
                         min(previous['ball'].confidence,current['ball'].confidence))
    return players, ball
