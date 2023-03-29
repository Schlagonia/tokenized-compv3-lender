import ape
from ape import Contract, reverts
from utils.checks import check_strategy_totals
from utils.utils import days_to_secs
import pytest


def test__weth_reward_selling(
    chain,
    weth,
    weth_amount,
    create_strategy,
    deposit,
    user,
    management,
    whale,
    keeper,
    comet_rewards,
    comp,
    comets,
):
    asset = weth
    amount = weth_amount
    comet = comets["weth"]

    strategy = create_strategy(asset, comet)

    # set uni fees for swap
    strategy.setUniFees(3000, 0, sender=management)
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

    tx = comet_rewards.getRewardOwed(comet, strategy.address, sender=user)
    rewards_owed = tx.return_value.owed
    assert rewards_owed > 0

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

    # Check we both claimed rewards and sold all of them
    tx = comet_rewards.getRewardOwed(comet, strategy.address, sender=user)
    rewards_owed = tx.return_value.owed
    assert rewards_owed == 0
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


def test__usdc_reward_selling(
    chain,
    create_strategy,
    deposit,
    user,
    management,
    whale,
    keeper,
    comet_rewards,
    comp,
    comets,
    tokens,
):
    asset = Contract(tokens["usdc"])
    comet = comets["usdc"]
    amount = int(100_000e6)

    strategy = create_strategy(asset, comet)

    # set uni fees for swap
    strategy.setUniFees(3000, 500, sender=management)
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

    comp_amount = int(1e18)
    comp.transfer(strategy, comp_amount, sender=whale)
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

    # Check we sold all of the comp
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


def test__set_min_amount_high__doesnt_sell(
    chain,
    asset,
    strategy,
    user,
    management,
    amount,
    whale,
    create_strategy,
    keeper,
    comp,
    comet,
    comets,
    tokens,
):
    asset = Contract(tokens["usdc"])
    comet = comets["usdc"]
    amount = int(100_000e6)

    strategy = create_strategy(asset, comet)

    # set uni fees for swap
    strategy.setUniFees(3000, 500, sender=management)

    # Set min to high for a sale
    min_amount = int(10_000e18)
    strategy.setMinAmountToSell(min_amount, sender=management)

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

    # Transfer some comp to the strategy
    comp_amount = int(1e18)
    comp.transfer(strategy, comp_amount, sender=whale)
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

    # Profit should still get reported but not sold comp
    assert comp.balanceOf(strategy) >= comp_amount

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
    assert comp.balanceOf(strategy) >= comp_amount

    # Lower min amount
    strategy.setMinAmountToSell(0, sender=management)

    # Report should now work even with no funds
    tx = strategy.report(sender=keeper)

    profit, loss = tx.return_value
    assert profit > 0

    assert comp.balanceOf(strategy) == 0
    assert strategy.totalDebt() > 0


def test__dont_set_uni_fees__reverts(
    chain,
    asset,
    strategy,
    user,
    management,
    amount,
    whale,
    keeper,
    comp,
    comet,
    comets,
    tokens,
    create_strategy,
):
    asset = Contract(tokens["usdc"])
    comet = comets["usdc"]
    amount = int(100_000e6)

    strategy = create_strategy(asset, comet)

    # Make sure fees are 0
    strategy.setUniFees(0, 0, sender=management)

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

    # Transfer some comp to the strategy
    comp_amount = int(1e18)
    comp.transfer(strategy, comp_amount, sender=whale)
    assert comp.balanceOf(strategy) == comp_amount

    before_pps = strategy.pricePerShare()

    with reverts():
        strategy.report(sender=keeper)

    # set uni fees for swap
    strategy.setUniFees(3000, 500, sender=management)

    # Now report should work
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

    # Profit should still get reported but not sold comp
    assert comp.balanceOf(strategy) == 0

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
