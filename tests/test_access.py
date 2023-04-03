import ape
from ape import Contract, reverts, project
from utils.checks import check_strategy_totals
from utils.utils import days_to_secs
import pytest


def test_deploy(management, comet, asset):
    strategy = management.deploy(project.CompoundV3Lender, asset, "YCompound V3", comet)


def test__set_uni_fees(
    chain,
    asset,
    strategy,
    management,
    comp,
    weth,
    tokens,
    comet,
    comets,
):
    if asset == weth:
        asset = tokens["usdc"]
        comet = comets["usdc"]
        strategy = create_strategy(asset, comet)

    # Everything should start as 0
    assert strategy.uniFees(comp, weth) == 0
    assert strategy.uniFees(weth, comp) == 0
    assert strategy.uniFees(weth, asset) == 0
    assert strategy.uniFees(asset, weth) == 0

    strategy.setUniFees(300, 500, sender=management)

    assert strategy.uniFees(comp, weth) == 300
    assert strategy.uniFees(weth, comp) == 300
    assert strategy.uniFees(weth, asset) == 500
    assert strategy.uniFees(asset, weth) == 500

    strategy.setUniFees(3, 5, sender=management)

    assert strategy.uniFees(comp, weth) == 3
    assert strategy.uniFees(weth, comp) == 3
    assert strategy.uniFees(weth, asset) == 5
    assert strategy.uniFees(asset, weth) == 5

    strategy.setUniFees(0, 0, sender=management)

    assert strategy.uniFees(comp, weth) == 0
    assert strategy.uniFees(weth, comp) == 0
    assert strategy.uniFees(weth, asset) == 0
    assert strategy.uniFees(asset, weth) == 0


def test__set_uni_fees__reverts(
    chain,
    asset,
    strategy,
    user,
    management,
    comp,
    weth,
    tokens,
    comet,
    comets,
):
    if asset == weth:
        asset = tokens["usdc"]
        comet = comets["usdc"]
        strategy = create_strategy(asset, comet)

    # Everything should start as 0
    assert strategy.uniFees(comp, weth) == 0
    assert strategy.uniFees(weth, comp) == 0
    assert strategy.uniFees(weth, asset) == 0
    assert strategy.uniFees(asset, weth) == 0

    with reverts("!Authorized"):
        strategy.setUniFees(300, 500, sender=user)

    assert strategy.uniFees(comp, weth) == 0
    assert strategy.uniFees(weth, comp) == 0
    assert strategy.uniFees(weth, asset) == 0
    assert strategy.uniFees(asset, weth) == 0


def test__set_min_amount_to_sell(
    chain,
    asset,
    strategy,
    management,
    user,
):
    assert strategy.minAmountToSell() == 1e12

    amount = 0

    strategy.setMinAmountToSell(amount, sender=management)

    assert strategy.minAmountToSell() == amount

    amount = int(100e18)

    strategy.setMinAmountToSell(amount, sender=management)

    assert strategy.minAmountToSell() == amount


def test__set_min_amount_to_sell__reverts(
    strategy,
    management,
    user,
):
    assert strategy.minAmountToSell() == 1e12

    with reverts("!Authorized"):
        strategy.setMinAmountToSell(0, sender=user)

    assert strategy.minAmountToSell() == 1e12


def test__emergency_withdraw__reverts(strategy, user, deposit, amount):
    with reverts("!Authorized"):
        strategy.emergencyWithdraw(100, sender=user)

    deposit()

    check_strategy_totals(
        strategy,
        total_assets=amount,
        total_debt=amount,
        total_idle=0,
        total_supply=amount,
    )

    with reverts("!Authorized"):
        strategy.emergencyWithdraw(100, sender=user)
