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
