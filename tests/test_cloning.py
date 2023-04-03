import ape
from ape import Contract, reverts, project
from utils.checks import check_strategy_totals, check_strategy_mins
from utils.utils import days_to_secs
import pytest


def test__clone__operation(
    chain,
    asset,
    comet,
    comets,
    tokens,
    strategy,
    user,
    management,
    rewards,
    whale,
    weth,
    amount,
    RELATIVE_APPROX,
    keeper,
):
    if asset == weth:
        asset = Contract(tokens["usdc"])
        comet = comets["usdc"]
        amount = int(100_000e6)

    tx = strategy.cloneCompoundV3Lender(
        asset, "yTest Clone", management, rewards, keeper, comet, sender=management
    )

    strategy = project.ITokenizedStrategy.at(tx.return_value)

    strategy.setPerformanceFee(0, sender=management)

    asset.transfer(user, amount, sender=whale)

    user_balance_before = asset.balanceOf(user)

    # Deposit to the strategy
    asset.approve(strategy, amount, sender=user)
    strategy.deposit(amount, user, sender=user)

    check_strategy_totals(
        strategy,
        total_assets=amount,
        total_debt=amount,
        total_idle=0,
        total_supply=amount,
    )

    chain.mine(10)

    # withdrawal
    strategy.withdraw(amount, user, user, sender=user)

    check_strategy_totals(
        strategy, total_assets=0, total_debt=0, total_idle=0, total_supply=0
    )

    assert (
        pytest.approx(asset.balanceOf(user), rel=RELATIVE_APPROX) == user_balance_before
    )


def test__clone__profitable_report(
    chain,
    asset,
    comet,
    comets,
    tokens,
    strategy,
    user,
    management,
    rewards,
    whale,
    weth,
    amount,
    RELATIVE_APPROX,
    keeper,
):

    comp_fee = 3000
    asset_fee = 500

    tx = strategy.cloneCompoundV3Lender(
        asset, "yTest Clone", management, rewards, keeper, comet, sender=management
    )

    strategy = project.ITokenizedStrategy.at(tx.return_value)

    strategy.setPerformanceFee(0, sender=management)

    # set uni fees for swap
    strategy.setUniFees(comp_fee, asset_fee, sender=management)
    # allow any amount of swaps
    strategy.setMinAmountToSell(0, sender=management)

    asset.transfer(user, amount, sender=whale)

    # Deposit to the strategy
    user_balance_before = asset.balanceOf(user)

    # Deposit to the strategy
    asset.approve(strategy, amount, sender=user)
    strategy.deposit(amount, user, sender=user)

    check_strategy_totals(
        strategy,
        total_assets=amount,
        total_debt=amount,
        total_idle=0,
        total_supply=amount,
    )

    # Earn some profit
    chain.mine(days_to_secs(5))

    before_pps = strategy.pricePerShare()

    tx = strategy.report(sender=keeper)

    profit, loss = tx.return_value
    assert profit > 0

    check_strategy_totals(
        strategy,
        total_assets=amount + profit,
        total_debt=amount + profit,
        total_idle=0,
        total_supply=amount + profit,
    )

    # needed for profits to unlock
    chain.pending_timestamp = (
        chain.pending_timestamp + strategy.profitMaxUnlockTime() - 1
    )
    chain.mine(timestamp=chain.pending_timestamp)

    check_strategy_totals(
        strategy,
        total_assets=amount + profit,
        total_debt=amount + profit,
        total_idle=0,
        total_supply=amount,
    )

    assert strategy.pricePerShare() > before_pps

    strategy.redeem(amount, user, user, sender=user)

    check_strategy_totals(
        strategy,
        total_assets=0,
        total_debt=0,
        total_idle=0,
        total_supply=0,
    )

    assert asset.balanceOf(user) > user_balance_before


def test__clone__reward_selling(
    chain,
    asset,
    comet,
    comets,
    tokens,
    strategy,
    user,
    management,
    rewards,
    whale,
    weth,
    amount,
    comp,
    comp_whale,
    RELATIVE_APPROX,
    keeper,
):

    comp_fee = 3000
    asset_fee = 500

    tx = strategy.cloneCompoundV3Lender(
        asset, "yTest Clone", management, rewards, keeper, comet, sender=management
    )

    strategy = project.ITokenizedStrategy.at(tx.return_value)

    strategy.setPerformanceFee(0, sender=management)

    asset.transfer(user, amount, sender=whale)

    # set uni fees for swap
    strategy.setUniFees(comp_fee, asset_fee, sender=management)
    # allow any amount of swaps
    strategy.setMinAmountToSell(0, sender=management)

    # Deposit to the strategy
    user_balance_before = asset.balanceOf(user)

    # Deposit to the strategy
    asset.approve(strategy, amount, sender=user)
    strategy.deposit(amount, user, sender=user)

    check_strategy_totals(
        strategy,
        total_assets=amount,
        total_debt=amount,
        total_idle=0,
        total_supply=amount,
    )

    # Earn some profit
    chain.mine(days_to_secs(5))

    # Send comp to strategy
    comp_amount = int(1e18)
    comp.transfer(strategy, comp_amount, sender=comp_whale)
    assert comp.balanceOf(strategy) == comp_amount

    before_pps = strategy.pricePerShare()

    tx = strategy.report(sender=keeper)

    profit, loss = tx.return_value

    assert profit > 0

    check_strategy_totals(
        strategy,
        total_assets=amount + profit,
        total_debt=amount + profit,
        total_idle=0,
        total_supply=amount + profit,
    )

    assert comp.balanceOf(strategy.address) == 0

    # needed for profits to unlock
    chain.pending_timestamp = (
        chain.pending_timestamp + strategy.profitMaxUnlockTime() - 1
    )
    chain.mine(timestamp=chain.pending_timestamp)

    check_strategy_totals(
        strategy,
        total_assets=amount + profit,
        total_debt=amount + profit,
        total_idle=0,
        total_supply=amount,
    )

    assert strategy.pricePerShare() > before_pps

    strategy.redeem(amount, user, user, sender=user)

    check_strategy_totals(
        strategy,
        total_assets=0,
        total_debt=0,
        total_idle=0,
        total_supply=0,
    )

    assert asset.balanceOf(user) > user_balance_before


def test__clone__shutdown(
    chain,
    asset,
    comet,
    comets,
    tokens,
    strategy,
    user,
    management,
    rewards,
    whale,
    weth,
    amount,
    RELATIVE_APPROX,
    keeper,
):
    if asset == weth:
        asset = Contract(tokens["usdc"])
        comet = comets["usdc"]
        amount = int(100_000e6)

    tx = strategy.cloneCompoundV3Lender(
        asset, "yTest Clone", management, rewards, keeper, comet, sender=management
    )

    strategy = project.ITokenizedStrategy.at(tx.return_value)

    asset.transfer(user, amount, sender=whale)

    strategy.setPerformanceFee(0, sender=management)

    user_balance_before = asset.balanceOf(user)

    # Deposit to the strategy
    asset.approve(strategy, amount, sender=user)
    strategy.deposit(amount, user, sender=user)

    check_strategy_totals(
        strategy,
        total_assets=amount,
        total_debt=amount,
        total_idle=0,
        total_supply=amount,
    )

    chain.mine(14)

    assert asset.balanceOf(strategy) == 0

    # Need to shutdown the strategy, withdraw and then report the updated balances
    strategy.shutdownStrategy(sender=management)
    strategy.emergencyWithdraw(amount, sender=management)
    strategy.report(sender=management)

    assert asset.balanceOf(strategy) >= amount
    check_strategy_mins(
        strategy,
        min_total_assets=amount,
        min_total_debt=0,
        min_total_idle=amount,
        min_total_supply=amount,
    )

    # withdrawal
    strategy.withdraw(amount, user, user, sender=user)

    assert (
        pytest.approx(asset.balanceOf(user), rel=RELATIVE_APPROX) == user_balance_before
    )


def test__clone__access(
    chain,
    asset,
    comet,
    comets,
    tokens,
    strategy,
    user,
    management,
    rewards,
    whale,
    weth,
    comp,
    amount,
    RELATIVE_APPROX,
    keeper,
):
    if asset == weth:
        asset = Contract(tokens["usdc"])
        comet = comets["usdc"]
        amount = int(100_000e6)

    tx = strategy.cloneCompoundV3Lender(
        asset, "yTest Clone", management, rewards, keeper, comet, sender=management
    )

    strategy = project.ITokenizedStrategy.at(tx.return_value)

    asset.transfer(user, amount, sender=whale)

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

    with reverts("!Authorized"):
        strategy.setUniFees(0, 0, sender=user)

    assert strategy.uniFees(comp, weth) == 300
    assert strategy.uniFees(weth, comp) == 300
    assert strategy.uniFees(weth, asset) == 500
    assert strategy.uniFees(asset, weth) == 500

    assert strategy.minAmountToSell() == 1e12

    amount = 0

    strategy.setMinAmountToSell(amount, sender=management)

    assert strategy.minAmountToSell() == amount

    with reverts("!Authorized"):
        strategy.setMinAmountToSell(int(1e12), sender=user)

    assert strategy.minAmountToSell() == 0

    with reverts("!Authorized"):
        strategy.emergencyWithdraw(100, sender=user)
