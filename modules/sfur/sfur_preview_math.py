"""Static Instancing math from Wilds .240906211; no Blender or file side effects."""
import numpy as np


def normalize(v, fallback=None):
    length = np.linalg.norm(v, axis=-1, keepdims=True)
    out = v / np.maximum(length, 1e-12)
    return np.where(length > 1e-10, out, 0 if fallback is None else fallback)


def bilinear_repeat(pixels, uv):
    """Blender bottom-up pixel rows and imported UVs; D3D V flip is already imported."""
    height, width = pixels.shape[:2]
    xy = np.mod(uv, 1.0) * (width, height) - .5
    lo = np.floor(xy).astype(np.int64)
    f = xy - lo
    x, y = lo[:, 0] % width, lo[:, 1] % height
    x1, y1 = (x + 1) % width, (y + 1) % height
    a = pixels[y, x] * (1-f[:, :1]) + pixels[y, x1] * f[:, :1]
    b = pixels[y1, x] * (1-f[:, :1]) + pixels[y1, x1] * f[:, :1]
    return a * (1-f[:, 1:2]) + b * f[:, 1:2]


def generate_shells(position, normal, tangent, bitangent, groom, flow, count,
                    height, bend_root, bend, normal_rate, push, stand):
    """One result per outer shell; base surface is kept on the original object.

    bitangent is the RE/D3D basis (opposite Blender's V-flipped UV bitangent).
    Guards on zero-vector normalization are preview stability additions.
    """
    n = normalize(normal)
    t = normalize(tangent)
    b = normalize(bitangent)
    xy = groom[:, :2] * 2 - 1
    z = np.sqrt(1 - np.clip(np.sum(xy*xy, axis=1), 0, 1))
    g = normalize(t*xy[:, :1] + b*xy[:, 1:2] + n*z[:, None], n)
    root = n + (g-n)*bend_root
    p = position.copy()
    prev = 0.
    positions, normals, tangents, bitangents, heights = [], [], [], [], []
    for k in range(count):
        h = .9 * min((k+1)/count, 1.)
        direction = normalize(root+(g-root)*(bend*h), n)
        p += direction * (height*groom[:, 2:3]*(h-prev))
        #Shortest-arc rotation from base normal to shell direction, with antipodal guard.
        axis = np.cross(n, direction)
        dot = np.clip(np.sum(n*direction, axis=1, keepdims=True), -1, 1)
        q = normalize(np.concatenate((axis, 1+dot), axis=1))
        opposite = dot[:, 0] < -.9999
        helper = np.zeros_like(n)
        helper[:, 0] = 1
        helper[np.abs(n[:, 0]) > .9] = (0, 1, 0)
        q[opposite, :3] = normalize(np.cross(n, helper))[opposite]
        q[opposite, 3] = 0
        qt = 2*np.cross(q[:, :3], t)
        rotated_t = t + q[:, 3:4]*qt + np.cross(q[:, :3], qt)
        sn = normalize(n+(direction-n)*normal_rate, n)
        st = normalize(t+(rotated_t-t)*normal_rate, t)
        sign = np.sign(np.sum(np.cross(n, t)*b, axis=1, keepdims=True))
        sb = normalize(np.cross(sn, st)) * sign
        fxy = 2*(flow[:, :2]-128/255)
        fz = np.sqrt(np.maximum(1-np.sum(fxy*fxy, axis=1), 1e-4))
        f = normalize(-st*fxy[:, :1]-sb*fxy[:, 1:2]+sn*fz[:, None], sn)
        d = normalize((1+stand)*sn-f, sn)
        positions.append(p + flow[:, 2:3]*h*push*d)
        normals.append(sn)
        tangents.append(st)
        bitangents.append(sb)
        heights.append(h)
        prev = h
    return positions, normals, tangents, bitangents, heights
