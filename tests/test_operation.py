import ape
from ape import Contract
from utils.checks import check_strategy_totals
from utils.utils import days_to_secs
import pytest


def test__operation(
    chain,
    asset,
    strategy,
    user,
    deposit,
    amount,
    RELATIVE_APPROX,
    keeper,
):
    user_balance_before = asset.balanceOf(user)

    # Deposit to the strategy
    deposit()

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


def test__profitable_report(
    chain,
    asset,
    strategy,
    deposit,
    user,
    management,
    amount,
    whale,
    RELATIVE_APPROX,
    keeper,
):
    # Deposit to the strategy
    user_balance_before = asset.balanceOf(user)

    # Deposit to the strategy
    deposit()

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


def test__tend_trigger(
    chain,
    strategy,
    asset,
    amount,
    deposit,
    keeper,
    user,
):
    # Check Trigger
    assert strategy.tendTrigger() == False

    # Deposit to the strategy
    deposit()

    # Check Trigger
    assert strategy.tendTrigger() == False

    chain.mine(days_to_secs(1))

    # Check Trigger
    assert strategy.tendTrigger() == False

    strategy.report(sender=keeper)

    # Check Trigger
    assert strategy.tendTrigger() == False

    # needed for profits to unlock
    chain.pending_timestamp = (
        chain.pending_timestamp + strategy.profitMaxUnlockTime() - 1
    )
    chain.mine(timestamp=chain.pending_timestamp)

    # Check Trigger
    assert strategy.tendTrigger() == False

    strategy.redeem(amount, user, user, sender=user)

    # Check Trigger
    assert strategy.tendTrigger() == False
