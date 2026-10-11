"""Court-plane geometry. Airborne object coordinates are not ground positions."""
import cv2
import numpy as np

DIMENSIONS = {'tennis': (8.23, 23.77), 'badminton': (5.18, 13.4)}


class PlayerCourtGuide:
    """Retain a provisional outline through line occlusion in a stable view.

    This guide selects players only. It is never a metric calibration.
    """
    def __init__(self, sport):
        self.sport = sport
        self.court = None
        self.reference = None
        self.shape = None

    def update(self, image):
        thumbnail = cv2.resize(image,(96,54)).astype(np.float32)
        if self.reference is not None:
            change = np.abs(thumbnail-self.reference).mean()/255
            if self.shape != image.shape or change > .12:
                self.court = None
                self.reference = None
        proposal = suggest_court(image)
        if proposal:
            self.court = Court(self.sport,proposal,image.shape)
            self.reference = thumbnail
            self.shape = image.shape
        return self.court

def validate_corners(corners):
    values = np.asarray(corners, dtype=np.float32)
    if values.shape != (4, 2) or not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
        raise ValueError('Supply four normalized corners between 0 and 1.')
    contour = values.reshape(-1, 1, 2)
    if not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < 0.02:
        raise ValueError('Court corners must form a non-crossing quadrilateral of useful size.')
    return values.tolist()

class Court:
    def __init__(self, sport, corners, shape):
        self.width, self.length = DIMENSIONS[sport]
        self.corners = validate_corners(corners)
        h, w = shape[:2]
        source = np.array(corners, np.float32) * [w, h]
        target = np.array([[0, 0], [self.width, 0], [self.width, self.length], [0, self.length]], np.float32)
        self.transform = cv2.getPerspectiveTransform(source.astype(np.float32), target)

    def project(self, point):
        return cv2.perspectiveTransform(np.array([[point]], np.float32), self.transform)[0, 0].tolist()

    def contains(self, point, tolerance=0.0):
        x, y = point
        return -tolerance <= x <= self.width + tolerance and -tolerance <= y <= self.length + tolerance

    def landing(self, image_point, uncertainty_px=3.0):
        """Map only a contact hypothesis; uncertain line calls return None.

        Ground homography is not a depth estimator. Never call this on an
        airborne point to decide whether a rally has ended.
        """
        ground = self.project(image_point)
        if not np.isfinite(ground).all():
            return ground, None
        offsets = [self.project((image_point[0] + dx, image_point[1] + dy))
                   for dx, dy in ((-uncertainty_px, 0), (uncertainty_px, 0), (0, -uncertainty_px), (0, uncertainty_px))]
        classifications = [self.contains(point, tolerance=0.025) for point in [ground, *offsets]]
        return ground, classifications[0] if all(value == classifications[0] for value in classifications) else None

    def side(self, point):
        return 'A' if point[1] >= self.length / 2 else 'B'

def suggest_court(image):
    """Propose the largest convex bright-line quadrilateral; user confirmation is required."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 145), (180, 90, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    area = image.shape[0] * image.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        polygon = cv2.approxPolyDP(contour, cv2.arcLength(contour, True) * 0.025, True)
        if len(polygon) == 4 and cv2.isContourConvex(polygon) and cv2.contourArea(polygon) > area * 0.12:
            points = polygon[:, 0, :].astype(float)
            top = points[np.argsort(points[:, 1])[:2]]
            bottom = points[np.argsort(points[:, 1])[2:]]
            ordered = np.array([top[np.argmin(top[:, 0])], top[np.argmax(top[:, 0])], bottom[np.argmax(bottom[:, 0])], bottom[np.argmin(bottom[:, 0])]])
            return (ordered / [image.shape[1], image.shape[0]]).tolist()
    return None
