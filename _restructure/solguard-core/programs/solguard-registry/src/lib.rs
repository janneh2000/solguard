//! SolGuard Registry — On-chain immutable alert history
//!
//! Every time SolGuard detects a program upgrade authority change,
//! a SHA-256 hash of the alert is written to Solana. This creates a
//! verifiable, tamper-proof record that the alert existed at a specific
//! point in time. Anyone can query the chain to verify SolGuard's
//! detection history.
//!
//! ## Security hardening (audit pass v2)
//! - Input validation on `risk_level` and `event_type` (bounded enums).
//! - Checked arithmetic on the alert counter to prevent overflow.
//! - `close_alert` rent-reclaim path gated behind registry authority.
//! - `pause` flag to stop further alert writes during incident response.
//! - `transfer_authority` with two-step handoff (propose + accept) so a
//!   hijacked authority can't silently hand ownership to an attacker.
//! - Anchor `has_one = authority` enforcement + explicit signer checks.

use anchor_lang::prelude::*;

// NOTE: After `anchor deploy` replace this with the real program id.
// Devnet: 5kkaYGaXECsngVohp3Z7NdDnxpfatTqSsmMVpsnngZFM
declare_id!("5kkaYGaXECsngVohp3Z7NdDnxpfatTqSsmMVpsnngZFM");

// ── Constants ────────────────────────────────────────────────────────────────
pub const MAX_RISK_LEVEL: u8 = 3;   // 0=LOW 1=MEDIUM 2=HIGH 3=CRITICAL
pub const MAX_EVENT_TYPE: u8 = 4;   // 0=SET_AUTHORITY 1=UPGRADE 2=INIT_BUFFER 3=DURABLE_NONCE 4=MULTISIG_CHANGE

#[program]
pub mod solguard_registry {
    use super::*;

    /// Initialize the global registry state. Called once by the SolGuard admin.
    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let registry = &mut ctx.accounts.registry;
        registry.authority = ctx.accounts.authority.key();
        registry.pending_authority = Pubkey::default();
        registry.total_alerts = 0;
        registry.paused = false;
        registry.bump = ctx.bumps.registry;
        msg!("SolGuard Registry initialized by {}", registry.authority);
        Ok(())
    }

    /// Record a new alert on-chain. Only callable by the registry authority.
    pub fn record_alert(
        ctx: Context<RecordAlert>,
        program_id: Pubkey,
        risk_level: u8,
        event_type: u8,
        alert_hash: [u8; 32],
        old_authority: Pubkey,
        new_authority: Pubkey,
    ) -> Result<()> {
        // ── Input validation ─────────────────────────────────────────
        require!(risk_level <= MAX_RISK_LEVEL, SolGuardError::InvalidRiskLevel);
        require!(event_type <= MAX_EVENT_TYPE, SolGuardError::InvalidEventType);

        let registry = &mut ctx.accounts.registry;
        require!(!registry.paused, SolGuardError::RegistryPaused);

        let alert = &mut ctx.accounts.alert;
        let clock = Clock::get()?;

        alert.registry = registry.key();
        alert.program_id = program_id;
        alert.risk_level = risk_level;
        alert.event_type = event_type;
        alert.alert_hash = alert_hash;
        alert.old_authority = old_authority;
        alert.new_authority = new_authority;
        alert.timestamp = clock.unix_timestamp;
        alert.slot = clock.slot;
        alert.alert_index = registry.total_alerts;

        // ── Checked arithmetic ───────────────────────────────────────
        registry.total_alerts = registry
            .total_alerts
            .checked_add(1)
            .ok_or(SolGuardError::CounterOverflow)?;

        msg!(
            "SolGuard Alert #{} recorded: program={}, risk={}, event={}",
            alert.alert_index,
            program_id,
            risk_level,
            event_type
        );

        emit!(AlertRecorded {
            alert_index: alert.alert_index,
            program_id,
            risk_level,
            event_type,
            alert_hash,
            timestamp: clock.unix_timestamp,
            slot: clock.slot,
        });

        Ok(())
    }

    /// Pause / unpause the registry. Pausing blocks new alert writes but
    /// does not affect existing records — used during incident response.
    pub fn set_paused(ctx: Context<AdminOp>, paused: bool) -> Result<()> {
        ctx.accounts.registry.paused = paused;
        msg!("Registry pause state -> {}", paused);
        Ok(())
    }

    /// Propose a new authority. Two-step handoff: the incumbent proposes,
    /// the proposed key must explicitly accept. Mitigates hijacked-key
    /// scenarios where an attacker could transfer ownership instantly.
    pub fn propose_authority(ctx: Context<AdminOp>, new_authority: Pubkey) -> Result<()> {
        ctx.accounts.registry.pending_authority = new_authority;
        msg!("Authority transfer proposed -> {}", new_authority);
        Ok(())
    }

    /// Accept a pending authority transfer. Must be signed by the proposed key.
    pub fn accept_authority(ctx: Context<AcceptAuthority>) -> Result<()> {
        let registry = &mut ctx.accounts.registry;
        require!(
            registry.pending_authority == ctx.accounts.new_authority.key(),
            SolGuardError::NotPendingAuthority
        );
        let old = registry.authority;
        registry.authority = ctx.accounts.new_authority.key();
        registry.pending_authority = Pubkey::default();
        msg!("Authority transferred {} -> {}", old, registry.authority);
        Ok(())
    }

    /// Close an alert account and reclaim rent. Useful for old low-risk
    /// alerts that no longer need on-chain presence. Only the authority.
    pub fn close_alert(_ctx: Context<CloseAlert>) -> Result<()> {
        msg!("Alert account closed and rent reclaimed");
        Ok(())
    }
}

// ── Accounts ─────────────────────────────────────────────────────────────────

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = authority,
        space = 8 + Registry::INIT_SPACE,
        seeds = [b"registry"],
        bump,
    )]
    pub registry: Account<'info, Registry>,
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(
    program_id: Pubkey,
    risk_level: u8,
    event_type: u8,
    alert_hash: [u8; 32],
)]
pub struct RecordAlert<'info> {
    #[account(
        mut,
        seeds = [b"registry"],
        bump = registry.bump,
        has_one = authority,
    )]
    pub registry: Account<'info, Registry>,
    #[account(
        init,
        payer = authority,
        space = 8 + AlertRecord::INIT_SPACE,
        seeds = [b"alert", registry.total_alerts.to_le_bytes().as_ref()],
        bump,
    )]
    pub alert: Account<'info, AlertRecord>,
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct AdminOp<'info> {
    #[account(
        mut,
        seeds = [b"registry"],
        bump = registry.bump,
        has_one = authority,
    )]
    pub registry: Account<'info, Registry>,
    pub authority: Signer<'info>,
}

#[derive(Accounts)]
pub struct AcceptAuthority<'info> {
    #[account(
        mut,
        seeds = [b"registry"],
        bump = registry.bump,
    )]
    pub registry: Account<'info, Registry>,
    pub new_authority: Signer<'info>,
}

#[derive(Accounts)]
pub struct CloseAlert<'info> {
    #[account(
        seeds = [b"registry"],
        bump = registry.bump,
        has_one = authority,
    )]
    pub registry: Account<'info, Registry>,
    #[account(
        mut,
        close = authority,
        has_one = registry,
    )]
    pub alert: Account<'info, AlertRecord>,
    #[account(mut)]
    pub authority: Signer<'info>,
}

// ── State ────────────────────────────────────────────────────────────────────

#[account]
#[derive(InitSpace)]
pub struct Registry {
    /// The authority (SolGuard agent wallet) that can record alerts
    pub authority: Pubkey,
    /// Two-step handoff target — must be explicitly accepted
    pub pending_authority: Pubkey,
    /// Total number of alerts recorded
    pub total_alerts: u64,
    /// Incident-response circuit breaker
    pub paused: bool,
    /// PDA bump
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct AlertRecord {
    pub registry: Pubkey,
    pub program_id: Pubkey,
    pub risk_level: u8,
    pub event_type: u8,
    pub alert_hash: [u8; 32],
    pub old_authority: Pubkey,
    pub new_authority: Pubkey,
    pub timestamp: i64,
    pub slot: u64,
    pub alert_index: u64,
}

// ── Events ───────────────────────────────────────────────────────────────────

#[event]
pub struct AlertRecorded {
    pub alert_index: u64,
    pub program_id: Pubkey,
    pub risk_level: u8,
    pub event_type: u8,
    pub alert_hash: [u8; 32],
    pub timestamp: i64,
    pub slot: u64,
}

// ── Errors ───────────────────────────────────────────────────────────────────

#[error_code]
pub enum SolGuardError {
    #[msg("Invalid risk level. Must be 0-3.")]
    InvalidRiskLevel,
    #[msg("Invalid event type. Must be 0-4.")]
    InvalidEventType,
    #[msg("Registry is paused — alerts cannot be recorded right now.")]
    RegistryPaused,
    #[msg("Alert counter overflow — registry has recorded u64::MAX alerts.")]
    CounterOverflow,
    #[msg("Signer is not the pending authority — transfer cannot be accepted.")]
    NotPendingAuthority,
}
