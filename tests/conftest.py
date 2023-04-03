import pytest
from ape import Contract, project


@pytest.fixture(scope="session")
def daddy(accounts):
    yield accounts[4]


@pytest.fixture(scope="session")
def user(accounts):
    yield accounts[0]


@pytest.fixture(scope="session")
def rewards(accounts):
    yield accounts[1]


@pytest.fixture(scope="session")
def management(accounts):
    yield accounts[2]


@pytest.fixture(scope="session")
def keeper(accounts):
    yield accounts[3]


@pytest.fixture(scope="session")
def tokens():
    tokens = {
        "weth": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "usdc": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    }
    yield tokens


@pytest.fixture(scope="session")
def comets():
    comets = {
        "usdc": "0xF25212E676D1F7F89Cd72fFEe66158f541246445",
    }
    yield comets


@pytest.fixture(scope="session")
def comet(comets):
    return project.Comet.at(comets["usdc"])


@pytest.fixture(scope="session")
def comet_rewards():
    yield project.CometRewards.at("0x45939657d1CA34A8FA39A924B71D28Fe8431e581")


@pytest.fixture(scope="session")
def comp():
    yield Contract("0x8505b9d2254A7Ae468c0E9dd10Ccea3A837aef5c")


@pytest.fixture(scope="session")
def comp_whale():
    yield Contract("0x45939657d1CA34A8FA39A924B71D28Fe8431e581")


@pytest.fixture(scope="session")
def asset(comet):
    yield Contract(comet.baseToken())


@pytest.fixture(scope="session")
def whale(accounts):
    # In order to get some funds for the token you are about to use,
    # The Balancer vault stays steady ballin on almost all tokens
    # NOTE: If `asset` is a balancer pool this may cause issues on amount checks.
    yield accounts["0xBA12222222228d8Ba445958a75a0704d566BF2C8"]


@pytest.fixture(scope="session")
def amount(asset, user, whale):
    amount = 100 * 10 ** asset.decimals()

    asset.transfer(user, amount, sender=whale)
    yield amount


@pytest.fixture(scope="session")
def weth(tokens):
    yield Contract(tokens["weth"])


@pytest.fixture(scope="session")
def weth_amount(user, weth):
    weth_amount = 10 ** weth.decimals()
    user.transfer(weth, weth_amount)
    yield weth_amount


@pytest.fixture(scope="session")
def create_strategy(management, keeper, rewards, asset, comet):
    def create_strategy(asset, _comet=comet, performanceFee=0):
        strategy = management.deploy(
            project.CompoundV3Lender, asset, "YCompound V3", _comet
        )
        strategy = project.ITokenizedStrategy.at(strategy.address)

        strategy.setPerformanceFeeRecipient(rewards, sender=management)
        strategy.setKeeper(keeper, sender=management)
        strategy.setPerformanceFee(performanceFee, sender=management)

        return strategy

    yield create_strategy


@pytest.fixture(scope="session")
def strategy(asset, create_strategy):
    strategy = create_strategy(asset)

    yield strategy


@pytest.fixture(scope="session")
def create_oracle(comet, management, weth):
    def create_oracle(c=comet, m=management):
        oracle = m.deploy(project.CompoundV3AprOracle, "YCompV3 oracle", c)

        if c.baseToken() == weth:
            oracle.setPriceFeeds(
                "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
                oracle.rewardTokenPriceFeed(),
                sender=m,
            )

        return oracle

    yield create_oracle


############ HELPER FUNCTIONS ############


@pytest.fixture(scope="session")
def deposit(strategy, asset, user, amount):
    def deposit(assets=amount, account=user):
        asset.approve(strategy, assets, sender=account)
        strategy.deposit(assets, account, sender=account)

    yield deposit


@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    yield 1e-5
