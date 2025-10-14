// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.23;

import "./utils/TestBase.sol";
import "./mocks/MockERC20.sol";
import "./mocks/MockAdapter.sol";
import "../Vault.sol";

contract VaultTest is TestBase {
    MockERC20 token;
    Vault vault;
    MockAdapter adapter;

    address admin;
    address manager;
    address guardian;
    address alice;
    address bob;

    function setUp() public {
        admin = address(0xA11CE);
        manager = address(0xB0B);
        guardian = address(0xF00D);
        alice = address(0xAAA1);
        bob = address(0xBBB2);

        token = new MockERC20("USD Stable", "USDS");
        adapter = new MockAdapter();

        // mint funds to test users
        token.mint(alice, 1_000_000 ether);
        token.mint(bob,   1_000_000 ether);

        // deploy vault
        vault = new Vault(
            address(token),
            "VaultCraft Shares",
            "VSHARE",
            admin,
            manager,
            guardian,
            false,
            1000, // 10%
            1 // 1 day
        );

        // admin set adapter allow
        vm.prank(admin);
        vault.setAdapter(address(adapter), true);
    }

    function _approve(address user, uint256 amt) internal {
        vm.prank(user);
        token.approve(address(vault), amt);
    }

    function test_deposit_minting_conserves_PS() public {
        // initial PS = 1e18
        assertEq(vault.ps(), 1e18, "ps0");

        // alice deposit 1000
        _approve(alice, 1000 ether);
        vm.prank(alice);
        vault.deposit(1000 ether, alice);
        uint256 ps1 = vault.ps();
        assertEq(ps1, 1e18, "ps after first deposit");
        assertEq(vault.totalAssets(), 1000 ether, "A=1000");
        assertEq(vault.balanceOf(alice), 1000 ether, "S(alice)=1000");

        // bob deposit 500 → PS stays same, shares=500
        _approve(bob, 500 ether);
        vm.prank(bob);
        vault.deposit(500 ether, bob);
        assertEq(vault.ps(), 1e18, "ps stays");
        assertEq(vault.balanceOf(bob), 500 ether, "S(bob)=500");
        assertEq(vault.totalAssets(), 1500 ether, "A=1500");
    }

    function test_withdraw_burn_conserves_PS() public {
        // setup two deposits
        _approve(alice, 1000 ether);
        vm.prank(alice); vault.deposit(1000 ether, alice);
        _approve(bob, 1000 ether);
        vm.prank(bob); vault.deposit(1000 ether, bob);

        // move time past lock (1 day)
        vm.warp(block.timestamp + 1 days + 1);

        // redeem 500 shares from alice
        vm.prank(alice);
        vault.redeem(500 ether, alice, alice);
        assertEq(vault.ps(), 1e18, "ps constant");
        assertEq(token.balanceOf(alice), 1_000_000 ether - 1000 ether + 500 ether, "alice asset");
    }

    function test_hwm_perf_fee_minting_only_when_PS_gt_HWM() public {
        // alice deposit 1000
        _approve(alice, 1000 ether);
        vm.prank(alice); vault.deposit(1000 ether, alice);
        assertEq(vault.ps(), 1e18, "ps=1");

        // donate profit 200 directly to vault (simulate pnl)
        token.mint(address(vault), 200 ether);
        // checkpoint to mint perf fee (10% of gain)
        uint256 S_before = vault.totalSupply(); // 1000
        vm.prank(manager);
        vault.checkpoint();

        // PS now = 1200/1000=1.2e18; HWM from 1e18 → 1.2e18
        // perfAssets = (1.2-1.0)*1000 * 10% = 200 * 10% = 20
        // perfShares = perfAssets / PS = 20 / 1.2 = 16.666...
        uint256 psNow = vault.ps();
        // within small tolerance
        assertApproxEq(psNow, 1_200_000_000_000_000_000, 1000, "ps ~ 1.2");

        uint256 S_after = vault.totalSupply();
        uint256 minted = S_after - S_before;
        // expect floor(20e18 / 1.2e18) = floor(16.666...) = 16
        // but due to integer math, check minted close to 16 or 17 depending rounding
        assertTrue(minted == 16 ether || minted == 17 ether, "perf shares ~ 16-17");
    }

    function test_private_vault_requires_whitelist() public {
        // deploy a private vault
        Vault pv = new Vault(
            address(token),
            "Private Shares",
            "PVSH",
            admin,
            manager,
            guardian,
            true,
            1000,
            1
        );
        // alice not whitelisted → deposit reverts
        _approve(alice, 100 ether);
        vm.prank(alice);
        bool reverted;
        try pv.deposit(100 ether, alice) returns (uint256) { reverted = false; } catch { reverted = true; }
        assertTrue(reverted, "should revert for non-wl");

        // admin whitelist alice
        vm.prank(admin);
        pv.setWhitelist(alice, true);
        // now ok
        vm.prank(alice);
        pv.deposit(100 ether, alice);
        assertEq(pv.balanceOf(alice), 100 ether, "wl deposit ok");
    }

    function test_lock_min_days_enforced() public {
        _approve(alice, 1000 ether);
        vm.prank(alice); vault.deposit(1000 ether, alice);
        // before unlock
        bool reverted;
        vm.prank(alice);
        try vault.redeem(1 ether, alice, alice) returns (uint256) { reverted=false; } catch { reverted=true; }
        assertTrue(reverted, "locked");
        // warp past lock
        vm.warp(block.timestamp + 1 days + 1);
        vm.prank(alice);
        vault.redeem(1 ether, alice, alice);
        assertEq(vault.balanceOf(alice), 999 ether, "redeemed 1");
    }

    function test_pause_blocks_actions() public {
        vm.prank(guardian); vault.pause();
        _approve(alice, 10 ether);
        vm.prank(alice);
        bool reverted;
        try vault.deposit(10 ether, alice) returns (uint256) { reverted=false; } catch { reverted=true; }
        assertTrue(reverted, "pause deposit blocked");
        vm.prank(guardian); vault.unpause();
        vm.prank(alice); vault.deposit(10 ether, alice);
        assertEq(vault.balanceOf(alice), 10 ether, "after unpause ok");
    }

    function test_execute_requires_whitelisted_adapter_and_manager() public {
        // not manager → revert
        bool reverted;
        vm.prank(alice);
        try vault.execute(address(adapter), abi.encode(int256(1), uint256(2), uint256(3))) returns (int256, uint256, uint256) { reverted=false; } catch { reverted=true; }
        assertTrue(reverted, "only manager");

        // manager, adapter allowed
        vm.prank(manager);
        (int256 pnl, uint256 spent, uint256 received) = vault.execute(address(adapter), abi.encode(int256(1), uint256(2), uint256(3)));
        assertEq(uint256(int256(pnl)), uint256(1), "pnl");
        assertEq(spent, 2, "spent");
        assertEq(received, 3, "received");
    }

    function test_execute_reverts_if_adapter_not_whitelisted() public {
        // deploy a fresh adapter that is not whitelisted
        MockAdapter bad = new MockAdapter();
        bool reverted;
        vm.prank(manager);
        try vault.execute(address(bad), abi.encode(int256(0), uint256(0), uint256(0))) returns (int256, uint256, uint256) { reverted=false; } catch { reverted=true; }
        assertTrue(reverted, "adapter not allowed");
    }
}
