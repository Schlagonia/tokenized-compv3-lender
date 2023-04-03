import ape
from ape import Contract, reverts, project
from utils.checks import check_strategy_totals
from utils.utils import days_to_secs
import pytest


def check_oracle(
    oracle, comet, asset, user, management, expected_base_token_price_feed, incentivized
):
    # Check set up
    assert oracle.rewardTokenPriceFeed() == "0xdbd020CAeF83eFd542f4De03e3cF0C28A4428bd5"
    assert oracle.baseTokenPriceFeed() == expected_base_token_price_feed
    assert oracle.comet() == comet.address
    assert oracle.baseToken() == asset.address

    current_apr = oracle.aprAfterDebtChange(asset.address, 0)

    assert current_apr > 0
    assert current_apr < int(1e18)

    reward_apr = oracle.getRewardAprForSupplyBase(comet.totalSupply())

    if incentivized:
        assert reward_apr > 0
        assert reward_apr < current_apr
    else:
        assert reward_apr == 0

    with reverts("Not today MoFo"):
        oracle.setPriceFeeds(
            oracle.baseTokenPriceFeed(), oracle.rewardTokenPriceFeed(), sender=user
        )

    baseToken = oracle.baseToken()

    with reverts():
        oracle.setPriceFeeds(baseToken, baseToken, sender=management)



def test__usdc_oracle(create_oracle, tokens, comets, user, management):
    comet = Contract(comets["usdc"])
    asset = Contract(tokens["usdc"])

    oracle = create_oracle(comet)

    check_oracle(
        oracle, comet, asset, user, management, comet.baseTokenPriceFeed(), False
    )
