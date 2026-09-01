"""Contratos de regressão do rig VRM executado no frontend."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_vrm1_pose_is_relative_to_normalized_rest_pose():
    """Offsets não podem voltar a substituir a rotação-base do modelo."""
    source = (ROOT / "ui/avatar/rig-core.js").read_text(encoding="utf-8")
    assert "normalizedRestPose" in source
    assert "this._qDelta" in source
    assert ".multiply(this.restQuaternion(name))" in source
    assert "n.rotation.set(v[0], v[1], v[2])" not in source


def test_arm_calibration_is_not_hardcoded_to_z_axis():
    source = (ROOT / "ui/avatar/rig-core.js").read_text(encoding="utf-8")
    assert "new THREE.Vector3(1, 0, 0)" in source
    assert "new THREE.Vector3(0, 1, 0)" in source
    assert "new THREE.Vector3(0, 0, 1)" in source
    assert "this.armCalibration = out" in source


def test_rig_profile_exposes_vrm1_capabilities():
    source = (ROOT / "ui/avatar/rig-profile.js").read_text(encoding="utf-8")
    for contract in ("version", "humanoidComplete", "lookAt", "expressions", "springBone", "nodeConstraints"):
        assert contract in source


def test_arm_ik_uses_mirrored_continuous_pole_and_safe_reach():
    source = (ROOT / "ui/avatar/solvers/ik.js").read_text(encoding="utf-8")
    assert "poleState" in source
    assert "mir * 0.82" in source
    assert "armLen * 0.97" in source
    assert "armLen * 0.16" in source
    assert "degToRad(110)" in source
    assert "side + 'Shoulder'" in source


def test_self_collision_keeps_hands_on_their_body_side():
    source = (ROOT / "ui/avatar/solvers/self-collision.js").read_text(encoding="utf-8")
    assert "minLateral = sw * 0.08" in source
    assert "bodyRight" in source


def test_motion_scheduler_deduplicates_and_respects_body_ownership():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js não disponível para testar o scheduler ES module")
    module_url = (ROOT / "ui/avatar/motion-scheduler.js").as_uri()
    script = f"""
      const {{ MotionScheduler }} = await import({module_url!r});
      const s = new MotionScheduler();
      const check = (v, msg) => {{ if (!v) throw new Error(msg); }};
      const first = s.request('raise_right', 0, {{ source:'user' }});
      check(first.accepted, 'primeiro gesto rejeitado');
      check(!s.request('raise_right', 0.2, {{ source:'user' }}).accepted, 'duplicata aceita');
      check(!s.request('raise_left', 0.3, {{ source:'behavior' }}).accepted, 'pose inferior interrompeu usuário');
      check(s.request('nod', 0.3, {{ source:'behavior' }}).accepted, 'cabeça não coexistiu com braço');
      check(s.request('raise_both', 0.4, {{ source:'debug' }}).accepted, 'prioridade superior não interrompeu');
      check(!s.request('rest', 0.5, {{ source:'sequence' }}).accepted, 'repouso antigo cancelou gesto novo');
      s.tick(3);
      check(!s.owns('pose') && !s.owns('head'), 'ownership não expirou');
    """
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_attention_controller_prioritizes_and_releases_smoothly():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js não disponível para testar a atenção")
    module_url = (ROOT / "ui/avatar/attention-controller.js").as_uri()
    script = f"""
      const {{ AttentionController }} = await import({module_url!r});
      const a = new AttentionController();
      const check = (v, msg) => {{ if (!v) throw new Error(msg); }};
      const scene = a.focus(1, 2, 3, 0, {{ source:'interaction', hold:2 }});
      check(scene.accepted, 'foco inicial rejeitado');
      check(!a.focus(4, 5, 6, 0.1, {{ source:'behavior' }}).accepted, 'prioridade menor interrompeu');
      const user = a.focus(7, 8, 9, 0.2, {{ source:'user' }});
      check(user.accepted, 'usuário não interrompeu interação');
      check(!a.release(scene.id), 'foco antigo liberou foco novo');
      a.update(0.3, 0.1);
      check(a.current.weight > 0, 'atenção não entrou suavemente');
      check(a.release(user.id, 'user'), 'foco atual não foi liberado');
      for (let i=0; i<30; i++) a.update(0.4+i/10, 0.1);
      check(a.current.weight < 0.01, 'atenção não saiu suavemente');
    """
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script], cwd=ROOT,
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_expression_profile_normalizes_vrm0_and_vrm1_names():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js não disponível para testar expressões VRM")
    module_url = (ROOT / "ui/avatar/rig-profile.js").as_uri()
    script = f"""
      const {{ createExpressionMap }} = await import({module_url!r});
      const v1 = createExpressionMap(['happy','sad','aa','ih','ou','ee','oh','blinkLeft']);
      const v0 = createExpressionMap(['joy','sorrow','a','i','u','e','o','blink_l']);
      if (v1.aa !== 'aa' || v1.blinkLeft !== 'blinkLeft') throw new Error('VRM1 incorreto');
      if (v0.happy !== 'joy' || v0.sad !== 'sorrow' || v0.aa !== 'a' || v0.oh !== 'o')
        throw new Error('fallback VRM0 incorreto');
    """
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script], cwd=ROOT,
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_lipsync_uses_all_vrm1_visemes_and_closes_persistent_weights():
    source = (ROOT / "ui/avatar/layers/lipsync.js").read_text(encoding="utf-8")
    for viseme in ("aa", "ih", "ou", "ee", "oh"):
        assert f"'{viseme}'" in source
    assert "buf.setExpr(name, cur[name] < 0.001 ? 0 : cur[name])" in source
