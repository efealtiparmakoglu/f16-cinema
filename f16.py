#!/usr/bin/env python3
# Blender 5.x: blender --background --python f16.py -- --mod hero
"""f16-cinema: F-16 Fighting Falcon — kodla insa edilen avci ucagi, havada."""

import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

# F-16C spec (Lockheed): uzunluk 15.03 m, kanat acikligi 9.96 m, yukseklik 5.09 m
UZUNLUK, ACIKLIK, YUKSEKLIK = 15.03, 9.96, 3.6  # yukseklik: ucus konfigurasyonu

SIL = {}


def malzeme(ad, renk, metalik=0.0, pürzlülük=0.4, kaplama=0.0, emisyon=0.0):
    if ad in SIL:
        return SIL[ad]
    m = bpy.data.materials.new(ad)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*renk, 1)
    b.inputs["Metallic"].default_value = metalik
    b.inputs["Roughness"].default_value = pürzlülük
    if "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = kaplama
    if emisyon > 0:
        b.inputs["Emission Color"].default_value = (*renk, 1)
        b.inputs["Emission Strength"].default_value = emisyon
    SIL[ad] = m
    return m


def _yumu(o):
    try:
        bpy.ops.object.shade_smooth()
        if hasattr(bpy.ops.object, "shade_auto_smooth"):
            bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
    except Exception:
        pass


def ekle(o):
    bpy.context.collection.objects.link(o)
    return o


def kutu(ad, boy, konum, rot=(0, 0, 0), mat=None, bevel=0.02, segments=2):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.name = ad
    o.scale = (boy[0] / 2, boy[1] / 2, boy[2] / 2)
    o.location = konum
    o.rotation_euler = rot
    if bevel > 0:
        b = o.modifiers.new("bevel", "BEVEL")
        b.width = bevel
        b.segments = segments
    if mat:
        o.data.materials.append(mat)
    _yumu(o)
    return o


def silindir(ad, r, derinlik, konum, rot=(0, 0, 0), mat=None, coz=40):
    bpy.ops.mesh.primitive_cylinder_add(vertices=coz, radius=r, depth=derinlik)
    o = bpy.context.active_object
    o.name = ad
    o.location = konum
    o.rotation_euler = rot
    if mat:
        o.data.materials.append(mat)
    _yumu(o)
    return o


def kanat_plakasi(ad, p0, p1, p2, p3, kalinlik=0.09, mat=None):
    """4 kose noktasindan swept kanat plakasi (solidify ile kalinlastirilir)."""
    mesh = bpy.data.meshes.new(ad)
    mesh.from_pydata([tuple(p) for p in (p0, p1, p2, p3)], [], [(0, 1, 2, 3)])
    o = ekle(bpy.data.objects.new(ad, mesh))
    s = o.modifiers.new("solidify", "SOLIDIFY")
    s.thickness = kalinlik
    if mat:
        o.data.materials.append(mat)
    _yumu(o)
    return o


def loft_x(kesitler, mat, ad="govde"):
    """X ekseni boyunca kesit halkalarini loft eder. kesit: (x, w, h, zc)."""
    rings = []
    for (x, w, h, zc) in kesitler:
        t = np.linspace(0, 2 * math.pi, 24, endpoint=False)
        py = w / 2 * np.cos(t)
        pz = h / 2 * np.sin(t) + zc
        rings.append([(x, py[j], pz[j]) for j in range(24)])
    verts = [p for ring in rings for p in ring]
    faces = []
    for s in range(len(rings) - 1):
        for j in range(24):
            j2 = (j + 1) % 24
            faces.append((s * 24 + j, s * 24 + j2,
                          (s + 1) * 24 + j2, (s + 1) * 24 + j))
    mesh = bpy.data.meshes.new(ad)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    o = ekle(bpy.data.objects.new(ad, mesh))
    sub = o.modifiers.new("subsurf", "SUBSURF")
    sub.levels = 2
    sub.render_levels = 2
    if mat:
        o.data.materials.append(mat)
    _yumu(o)
    return o


def kol(ad, p0, p1, r, mat):
    p0, p1 = Vector(p0), Vector(p1)
    v = p1 - p0
    rot = v.to_track_quat("Z", "Y").to_euler()
    return silindir(ad, r, v.length, tuple((p0 + p1) / 2), rot=rot, mat=mat, coz=12)


def metin(ad, icerik, boyut, konum, rot, mat):
    bpy.ops.object.text_add()
    o = bpy.context.active_object
    o.name = ad
    o.data.body = icerik
    o.data.size = boyut
    o.data.extrude = 0.01
    o.data.align_x = "CENTER"
    o.location = konum
    o.rotation_euler = rot
    o.data.materials.append(mat)
    return o


# ---------------------------------------------------------------- insa

def insa(cfg):
    M = {}
    M["govde"] = malzeme("govde_boya", cfg["livery"]["govde"], 0.25, 0.5)
    M["koyu"] = malzeme("koyu", cfg["livery"]["koyu"], 0.1, 0.55)
    M["radom"] = malzeme("radom", cfg["livery"]["radom"], 0.0, 0.6)
    M["cam"] = malzeme("kokpit_cam", (0.9, 0.7, 0.25), 0.6, 0.08, kaplama=1.0)
    M["metal"] = malzeme("metal", (0.35, 0.36, 0.4), 1.0, 0.35)
    M["koyu_metal"] = malzeme("koyu_metal", (0.12, 0.12, 0.14), 1.0, 0.45)
    M["fuzeler"] = malzeme("fuze", (0.85, 0.85, 0.88), 0.3, 0.3)
    M["bulut"] = malzeme("bulut", (1, 1, 1), 0, 1)
    M["ab_ic"] = malzeme("ab_ic", (0.5, 0.7, 1.0), 0, 0.3, emisyon=5)
    M["ab_dis"] = malzeme("ab_dis", (1.0, 0.55, 0.15), 0, 0.4, emisyon=2.5)
    P = {}

    # ---------- govde loft (burun -7.5 -> nozzle +7.4)
    kesitler = [
        (-6.6, 0.04, 0.04, 0.05),
        (-6.1, 0.3, 0.3, 0.05),
        (-5.3, 0.55, 0.55, 0.05),
        (-4.6, 0.72, 0.75, 0.1),
        (-3.9, 0.82, 1.0, 0.15),
        (-3.2, 0.9, 1.12, 0.08),
        (-2.3, 0.98, 1.22, 0.0),
        (-1.4, 1.04, 1.28, -0.05),
        (-0.35, 1.06, 1.3, -0.05),
        (0.7, 1.04, 1.26, -0.05),
        (1.76, 0.98, 1.2, -0.02),
        (2.8, 0.92, 1.12, 0.0),
        (3.87, 0.84, 1.02, 0.0),
        (4.93, 0.72, 0.9, 0.0),
        (5.81, 0.58, 0.74, 0.0),
        (6.42, 0.46, 0.6, 0.0),
    ]
    P["govde"] = loft_x(kesitler, M["govde"], "govde")

    # kokpit kabini (altin cam)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0)
    canopy = bpy.context.active_object
    canopy.name = "kokpit"
    canopy.scale = (1.15, 0.4, 0.42)
    canopy.location = (-4.9, 0, 0.78)
    canopy.data.materials.append(M["cam"])
    _yumu(canopy)
    P["kokpit"] = canopy

    # hava aligi (cin intake)
    P["intake"] = kutu("intake", (2.2, 1.1, 0.55), (-2.4, 0, -0.72),
                       mat=M["govde"], bevel=0.1)

    # ---------- kanatlar (swept, mid-mounted)
    y_kok_ust = 0.52
    kok_on = (-0.6, y_kok_ust, -0.1)
    kok_arka = (2.4, y_kok_ust, -0.1)
    uc_on = (2.0, 4.98, 0.55)
    uc_arka = (2.9, 4.98, -0.25)
    P["kanat_s"] = kanat_plakasi(
        "kanat_s", kok_on, uc_on, uc_arka, kok_arka, 0.09, M["govde"])
    P["kanat_p"] = kanat_plakasi(
        "kanat_p",
        [kok_on[0], -kok_on[1], kok_on[2]], [uc_on[0], -uc_on[1], uc_on[2]],
        [uc_arka[0], -uc_arka[1], uc_arka[2]], [kok_arka[0], -kok_arka[1], kok_arka[2]],
        0.09, M["govde"])

    # kanat ucu fuzeleri (AIM-9) + raylar
    for sx in (-1, 1):
        ray = kutu(f"ray_{sx}", (2.4, 0.08, 0.09), (1.9, sx * 4.9, 0.15), mat=M["koyu"])
        P[f"fuze_govde_{sx}"] = silindir(
            f"fuze_{sx}", 0.075, 2.4, (1.9, sx * 4.9, 0.32),
            rot=(0, math.radians(90), 0), mat=M["fuzeler"])
        P[f"fuze_burun_{sx}"] = silindir(
            f"fuzeburun_{sx}", 0.075, 0.5, (3.35, sx * 4.9, 0.32),
            rot=(0, math.radians(-90), 0), mat=M["koyu"], coz=20)

    # ---------- dikey stabilizator (tek kuyruk)
    P["kuyruk"] = kanat_plakasi(
        "kuyruk", (4.1, 0, 0.9), (6.2, 0, 0.62), (6.35, 0, 2.68), (5.8, 0, 2.7),
        0.12, M["govde"])
    P["kuyruk_koke"] = kanat_plakasi(
        "kuyrukkoke", (3.2, 0, 0.42), (6.0, 0, 0.6), (6.1, 0, 0.48), (3.3, 0, 0.38),
        0.1, M["koyu"])

    # ---------- yatay stabilizatorler
    for sx in (-1, 1):
        P[f"stabil_{sx}"] = kanat_plakasi(
            f"stabil_{sx}", (4.95, sx * 0.5, 0.1), (6.43, sx * 2.6, 0.2),
            (6.3, sx * 2.6, -0.12), (6.07, sx * 0.5, -0.1), 0.08, M["govde"])

    # ---------- ventral finler
    for sx in (-1, 1):
        P[f"ventral_{sx}"] = kanat_plakasi(
            f"ventral_{sx}", (3.0, sx * 0.55, -0.55), (4.58, sx * 0.62, -1.02),
            (4.76, sx * 0.62, -0.6), (3.18, sx * 0.55, -0.5), 0.07, M["govde"])

    # ---------- nozzle + art yakici
    P["nozzle"] = silindir("nozzle", 0.5, 1.0, (6.9, 0, 0),
                           rot=(0, math.radians(90), 0), mat=M["koyu_metal"], coz=32)
    P["ab_cekirdek"] = silindir("ab_cekirdek", 0.3, 2.0, (8.2, 0, 0),
                                rot=(0, math.radians(90), 0), mat=M["ab_ic"], coz=24)
    P["ab_dis"] = silindir("ab_dis", 0.46, 1.5, (7.7, 0, 0),
                           rot=(0, math.radians(90), 0), mat=M["ab_dis"], coz=24)

    # ---------- burun pitot
    P["pitot"] = kol("pitot", (-6.7, 0, 0.05), (-7.55, 0, 0.05), 0.03, M["metal"])

    # ---------- kuyruk numarasi
    metin("kuyruk_no", cfg["number"], 1.1, (6.75, 0.08, 2.0),
          (math.radians(90), 0, math.radians(-90)), M["koyu"])

    return P, M


# ---------------------------------------------------------------- bulutlar + ucus

def bulutlar_uret(cfg, n_bulut):
    rng = np.random.default_rng(cfg.get("seed", 7))
    bulut_mat = malzeme("bulut_mal", (1, 1, 1), 0, 1)
    bulutlar = []
    for i in range(n_bulut):
        x = rng.uniform(-40, 140)
        y = rng.uniform(-90, 90)
        z = rng.uniform(-25, -8) if rng.random() < 0.5 else rng.uniform(10, 30)
        boyut = rng.uniform(6, 16)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=boyut)
        o = bpy.context.active_object
        o.name = f"bulut_{i}"
        o.location = (x, y, z)
        o.scale = (1, rng.uniform(0.6, 1), rng.uniform(0.3, 0.55))
        o.rotation_euler = (0, 0, rng.random() * 3)
        o.data.materials.append(bulut_mat)
        _yumu(o)
        bulutlar.append(o)
    return bulutlar


# ---------------------------------------------------------------- dogrulama

def spec_dogrula():
    print("== F-16C SPEC DOGRULAMA ==")
    hata = 0

    def olc(ad, gercek, beklenen, tol):
        nonlocal hata
        tamam = abs(gercek - beklenen) <= tol
        print(f"  [{'ok' if tamam else 'FAIL'}] {ad}: {gercek:.2f} m (spec {beklenen:.2f} ± {tol})")
        if not tamam:
            hata += 1

    mins = np.array([1e9] * 3)
    maks = -np.array([1e9] * 3)
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.name.startswith("bulut") or o.name.startswith("ab_"):
            continue
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v)
            mins = np.minimum(mins, np.array(w))
            maks = np.maximum(maks, np.array(w))
    olc("uzunluk (burun-nozzle)", maks[0] - mins[0], UZUNLUK, 0.35)
    olc("kanat acikligi", maks[1] - mins[1], ACIKLIK, 0.25)
    olc("yukseklik", maks[2] - mins[2], YUKSEKLIK, 0.15)
    fuzeler = [o for o in bpy.data.objects if "fuze" in o.name]
    olc("fuze sayisi (2x AIM-9)", len(fuzeler), 4, 0)
    nozzle = "nozzle" in bpy.data.objects
    kontrol("nozzle var", nozzle)
    kokpit = "kokpit" in bpy.data.objects
    kontrol("kokpit var", kokpit)
    if hata:
        sys.exit(1)


# ---------------------------------------------------------------- sahne kurulum

def sahne_kur(cfg):
    sc = bpy.context.scene
    dunya = bpy.data.worlds.new("Gokyuzu")
    sc.world = dunya
    dunya.use_nodes = True
    bg = dunya.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*cfg["sky"]["alt"], 1)
    bg.inputs[1].default_value = cfg["sky"]["guc"]
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for dv in prefs.devices:
            dv.use = True
        sc.cycles.device = "GPU"
    except Exception as e:
        print("  [uyari] GPU:", e)
    sc.cycles.samples = cfg["render"].get("spp", 64)
    sc.cycles.use_denoising = True
    sc.render.resolution_x = cfg["render"].get("width", 960)
    sc.render.resolution_y = cfg["render"].get("height", 540)
    sc.view_settings.view_transform = "Standard"
    gunes = bpy.data.lights.new("gunes", "SUN")
    gunes.energy = cfg.get("gunes", 6)
    gunes.angle = math.radians(2)
    go = bpy.data.objects.new("gunes", gunes)
    bpy.context.collection.objects.link(go)
    go.rotation_euler = (math.radians(55), 0, math.radians(150))
    return sc


def kamera_kur(konum, hedef, lens=70):
    cam = bpy.data.cameras.new("Cam")
    cam.lens = lens
    co = bpy.data.objects.new("kamera", cam)
    bpy.context.collection.objects.link(co)
    co.location = konum
    yon = Vector(hedef) - Vector(konum)
    co.rotation_euler = yon.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = co
    return co


# ---------------------------------------------------------------- ana

def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--mod", default="hero")
    ap.add_argument("--cfg", default="ucak.json")
    a = ap.parse_args(args)

    cfg = json.load(open(a.cfg, encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sahne_kur(cfg)
    P, M = insa(cfg)

    # tum ucaagi bos bir parent'a topla (animasyon icin)
    parent = bpy.data.objects.new("UCAK", None)
    bpy.context.collection.objects.link(parent)
    for o in bpy.data.objects:
        if o.name.startswith("bulut") or o.name == "UCAK":
            continue
        if o.parent is None:
            o.parent = parent

    if a.mod == "spec":
        spec_dogrula()
        return

    bulutlar = bulutlar_uret(cfg, 26)

    sc = bpy.context.scene
    W = cfg["render"].get("width", 960)
    H = cfg["render"].get("height", 540)
    spp = cfg["render"].get("spp", 64)
    sc.render.resolution_x = W
    sc.render.resolution_y = H

    os.makedirs("renders", exist_ok=True)

    if a.mod == "hero":
        km = cfg.get("camera", {})
        kamera_kur(km.get("hero_pos", [-11.5, -8.5, 2.6]),
                   km.get("hero_target", [-1, 0, 0.4]), km.get("hero_lens", 65))
        ab_i = bpy.data.objects["ab_cekirdek"]
        ab_d = bpy.data.objects["ab_dis"]
        for f in range(cfg["render"].get("frames", 36)):
            r = np.random.default_rng(f)
            ab_i.scale = (1, 1, 1.6 + r.uniform(-0.25, 0.35))
            ab_d.scale = (1, 1, 1.15 + r.uniform(-0.15, 0.2))
            for b in bulutlar:
                b.location.x -= 1.1
            sc.render.filepath = f"renders/ucus/f{f:04d}.png"
            os.makedirs(os.path.dirname(sc.render.filepath), exist_ok=True)
            bpy.ops.render.render(write_still=True)
            print(f"  kare {f + 1}/{cfg['render'].get('frames', 36)}")
        subprocess = __import__("subprocess")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "16",
                        "-i", "renders/ucus/f%04d.png",
                        "-vf", "palettegen=max_colors=256", "/tmp/pal.png"], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "16",
                        "-i", "renders/ucus/f%04d.png", "-i", "/tmp/pal.png",
                        "-lavfi", "paletteuse=dither=bayer:bayer_scale=3",
                        "-loop", "0", "renders/ucus.gif"], check=True)
        print("== BİTTİ -> renders/ucus.gif")
    elif a.mod == "acilar":
        km = cfg.get("camera", {})
        acilar = [("hero", tuple(km.get("hero_pos", [-13.5, -10.5, 3.6])),
                   tuple(km.get("hero_target", [-1.5, 0, 0.3])), km.get("hero_lens", 50)),
                  ("ustten", (0, -2, 14), (0, 0, 0), 60),
                  ("nozzle", (13, -3, 1.6), (7.4, 0, 0), 80),
                  ("kokpit", (-8.2, -3.4, 2.2), (-4.4, 0, 0.9), 85)]
        for ad, konum, hedef, lens in acilar:
            kamera_kur(konum, hedef, lens)
            sc.render.filepath = f"renders/{ad}.png"
            bpy.ops.render.render(write_still=True)
            print("== BİTTİ ->", sc.render.filepath)


if __name__ == "__main__":
    main()
