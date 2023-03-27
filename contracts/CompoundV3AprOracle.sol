// SPDX-License-Identifier: GPL-3.0
pragma solidity 0.8.18;

import {AprOracleBase} from "./helpers/AprOracleBase.sol";

import {Comet, CometRewards} from "./interfaces/Compound/V3/CompoundV3.sol";

contract CompoundV3AprOracle is AprOracleBase {
    Comet public comet;

    // price feeds for the reward apr calculation, can be updated manually if needed
    address public rewardTokenPriceFeed;
    address public baseTokenPriceFeed;

    uint64 internal constant DAYS_PER_YEAR = 365;
    uint64 internal constant SECONDS_PER_DAY = 60 * 60 * 24;
    uint64 internal constant SECONDS_PER_YEAR = 365 days;

    uint256 internal SCALER;

    constructor(string memory _name, address _comet) AprOracleBase(_name) {
        init(_comet);
    }

    function cloneCompoundV3AprOracle(
        string memory _name,
        address _comet
    ) external returns (address _newOracle) {
        _newOracle = _clone(_name);
        CompoundV3AprOracle(_newOracle).init(_comet);
    }

    function init(address _comet) public {
        require(address(comet) == address(0), "already initialized");
        comet = Comet(_comet);

        uint256 BASE_MANTISSA = comet.baseScale();
        uint256 BASE_INDEX_SCALE = comet.baseIndexScale();

        // this is needed for reward apr calculations based on decimals
        // of baseToken we scale rewards per second to the base token
        // decimals and diff between comp decimals and the index scale
        SCALER = (BASE_MANTISSA * 1e18) / BASE_INDEX_SCALE;

        // set default price feeds
        baseTokenPriceFeed = comet.baseTokenPriceFeed();
        // default to COMP/USD
        rewardTokenPriceFeed = 0xdbd020CAeF83eFd542f4De03e3cF0C28A4428bd5;
    }

    function setPriceFeeds(
        address _baseTokenPriceFeed,
        address _rewardTokenPriceFeed
    ) external onlyOwner {
        // just check the call doesnt revert. We dont care about the amount returned
        comet.getPrice(_baseTokenPriceFeed);
        comet.getPrice(_rewardTokenPriceFeed);
        baseTokenPriceFeed = _baseTokenPriceFeed;
        rewardTokenPriceFeed = _rewardTokenPriceFeed;
    }

    function aprAfterDebtChange(
        int256 _delta
    ) external view override returns (uint256) {
        uint256 borrows = comet.totalBorrow();
        uint256 supply = comet.totalSupply();

        uint256 newAmount = uint256(int256(supply) + _delta);

        uint256 newUtilization = (borrows * 1e18) / newAmount;

        unchecked {
            return
                getSupplyApr(newUtilization) +
                getRewardAprForSupplyBase(newAmount);
        }
    }

    function getRewardAprForSupplyBase(
        uint256 _newAmount
    ) public view returns (uint256) {
        Comet _comet = comet;
        unchecked {
            uint256 rewardToSuppliersPerDay = _comet.baseTrackingSupplySpeed() *
                SECONDS_PER_DAY *
                SCALER;
            if (rewardToSuppliersPerDay == 0) return 0;
            return
                ((_comet.getPrice(rewardTokenPriceFeed) *
                    rewardToSuppliersPerDay) /
                    (_newAmount * _comet.getPrice(baseTokenPriceFeed))) *
                DAYS_PER_YEAR;
        }
    }

    function getSupplyApr(uint256 _newUtilization) public view returns (uint) {
        unchecked {
            return
                comet.getSupplyRate(
                    _newUtilization // New utilization
                ) * SECONDS_PER_YEAR;
        }
    }
}
