import { expect } from "chai";
import { ethers } from "hardhat";

describe("Vault (Hardhat minimal)", function () {
  it("deploys and allows deposit/redeem after lock", async function () {
    const [admin, manager, guardian, alice] = await ethers.getSigners();

    // Deploy mock token
    const MockERC20 = await ethers.getContractFactory("MockERC20");
    const token = await MockERC20.deploy("USD Stable", "USDS");
    await token.waitForDeployment();

    // Mint to alice
    await (await token.mint(alice.address, ethers.parseEther("1000"))).wait();

    // Deploy vault
    const Vault = await ethers.getContractFactory("Vault");
    const vault = await Vault.deploy(
      await token.getAddress(),
      "VaultCraft Shares",
      "VSHARE",
      admin.address,
      manager.address,
      guardian.address,
      false,
      1000,
      1
    );
    await vault.waitForDeployment();

    // Approve & deposit
    await (await token.connect(alice).approve(await vault.getAddress(), ethers.parseEther("100"))).wait();
    await (await vault.connect(alice).deposit(ethers.parseEther("100"), alice.address)).wait();
    expect(await vault.balanceOf(alice.address)).to.equal(ethers.parseEther("100"));

    // Increase time by 1 day to pass lock
    await ethers.provider.send("evm_increaseTime", [24 * 60 * 60 + 10]);
    await ethers.provider.send("evm_mine", []);
    await (await vault.connect(alice).redeem(ethers.parseEther("10"), alice.address, alice.address)).wait();
    expect(await vault.balanceOf(alice.address)).to.equal(ethers.parseEther("90"));
  });
});
