"""깨끗한 래스터를 스캔본처럼 열화시킨다: 기울기, 흐림, 잡음, JPEG 압축."""
import sys, cv2, numpy as np
def main(src, dst, angle=0.4, seed=0):
    rng = np.random.default_rng(seed)
    im = cv2.imread(src, cv2.IMREAD_GRAYSCALE)
    h, w = im.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    im = cv2.warpAffine(im, M, (w, h), borderValue=255)
    im = cv2.GaussianBlur(im, (3, 3), 0.8)
    noise = rng.normal(0, 12, im.shape)
    im = np.clip(im.astype(np.float32) * 0.92 + 10 + noise, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode('.jpg', im, [cv2.IMWRITE_JPEG_QUALITY, 45])
    im = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    cv2.imwrite(dst, im)
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
