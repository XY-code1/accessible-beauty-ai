import pytest

from app.models import BeautyParameters, BeautyProfile, Step
from app.services.plan_engine import OMISSION_REASONS, PlanEngine


@pytest.mark.parametrize(
    "scene,style,intensity,skin_type,omissions,total",
    [
        ("work", "matte", "medium", "normal", {}, 360),
        ("daily", "matte", "medium", "normal", {Step.DEFINE: "daily_scene"}, 300),
        ("date", "matte", "medium", "normal", {Step.DEFINE: "natural_style"}, 300),
        ("work", "natural", "medium", "normal", {Step.DEFINE: "natural_style"}, 300),
        ("work", "matte", "light", "normal", {Step.DEFINE: "light_intensity"}, 209),
        ("work", "matte", "medium", "sensitive", {Step.SHAPE: "sensitive_skin"}, 240),
        (
            "daily", "natural", "light", "sensitive",
            {Step.DEFINE: "daily_scene", Step.SHAPE: "sensitive_skin"}, 125,
        ),
        ("party", "bold", "full", "oily", {}, 468),
    ],
)
def test_omitted_steps_do_not_contribute_to_total_duration(
    scene, style, intensity, skin_type, omissions, total
):
    engine = PlanEngine([])
    params = BeautyParameters(scene=scene, style=style, intensity=intensity)
    profile = BeautyProfile(skinType=skin_type, skinTags=[skin_type])
    base_steps = engine._layer1_base_steps(params)

    steps, total_duration, omitted_count = engine.generate_plan(params, profile)

    assert [step.step for step in steps] == [step.step for step in base_steps]
    for step, base_step in zip(steps, base_steps):
        assert step.essential == (step.step not in omissions)
        if step.step in omissions:
            assert step.duration == 0
            assert step.omittedReason == OMISSION_REASONS[step.step][omissions[step.step]]
        else:
            assert step.duration == base_step.duration
            assert step.omittedReason is None
    assert omitted_count == len(omissions)
    assert total_duration == total
    assert total_duration == sum(step.duration for step in steps if step.essential)


def test_pruning_zeros_preexisting_nonessential_step_without_mutating_input():
    engine = PlanEngine([])
    params = BeautyParameters(scene="work", style="matte", intensity="medium")
    steps = engine._layer1_base_steps(params)
    steps[0].essential = False
    steps[0].omittedReason = "Already prepared"

    pruned_steps = engine._layer2_minimal_pruning(steps, params, None)

    assert pruned_steps[0].duration == 0
    assert pruned_steps[0].omittedReason == "Already prepared"
    assert steps[0].duration == 60
