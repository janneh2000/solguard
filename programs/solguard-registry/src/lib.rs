use anchor_lang::prelude::*;

declare_id!("5kkaYGaXECsngVohp3Z7NdDnxpfatTqSsmMVpsnngZFM");

/// SolGuard Registry — On-chain immutable alert history
///
/// Every time SolGuard detects a program upgrade authority change,
/// a hash of the alert is written to Solana. This creates a verifiable,
/// tamper-proof record that the alert existed at a specific point in time.
///
/// Anyone can query the chain to verify SolGuard's detection history.
#[program]
pub mod solguard_registry {
    use super::*;

    /// Initialize the global registry state.
    /// Called once by the SolGuard admin.
    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let registry = &mut ctx.accounts.registry;
        registry.authority = ctx.accounts.authority.key();
        registry.total_alerts = 0;
        registry.bump = ctx.bumps.registry;
        msg!("SolGuard Registry initialized");
        Ok(())
    }

    /// Record a new alert on-chain.
    /// Only callable by the registry authority (SolGuard agent).
    pub fn record_alert(
        ctx: Context<RecordAlert>,
        program_id: Pubkey,
        risk_level: u8,
        event_type: u8,
        alert_hash: [u8; 32],
        old_authority: Pubkey,
        new_authority: Pubkey,
    ) -> Result<()> {
        let alert = &mut ctx.accounts.alert;
        let registry = &mut ctx.accounts.registry;
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

        registry.total_alerts += 1;

        msg!(
            "SolGuard Alert #{} recorded: program={}, risk={}",
            alert.alert_index,
            program_id,
            risk_level
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
        seeds = [
            b"alert",
            registry.total_alerts.to_le_bytes().as_ref(),
        ],
        bump,
    )]
    pub alert: Account<'info, AlertRecord>,
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

// ── State ────────────────────────────────────────────────────────────────────

#[account]
#[derive(InitSpace)]
pub struct Registry {
    /// The authority (SolGuard agent wallet) that can record alerts
    pub authority: Pubkey,
    /// Total number of alerts recorded
    pub total_alerts: u64,
    /// PDA bump
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct AlertRecord {
    /// Parent registry
    pub registry: Pubkey,
    /// The program that triggered the alert
    pub program_id: Pubkey,
    /// Risk level: 0=LOW, 1=MEDIUM, 2=HIGH, 3=CRITICAL
    pub risk_level: u8,
    /// Event type: 0=SET_AUTHORITY, 1=UPGRADE, 2=INITIALIZE_BUFFER
    pub event_type: u8,
    /// SHA-256 hash of the full alert JSON (off-chain verification)
    pub alert_hash: [u8; 32],
    /// Previous upgrade authority
    pub old_authority: Pubkey,
    /// New upgrade authority
    pub new_authority: Pubkey,
    /// Unix timestamp of the alert
    pub timestamp: i64,
    /// Solana slot when recorded
    pub slot: u64,
    /// Sequential alert index
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

// ── Error codes ──────────────────────────────────────────────────────────────

#[error_code]
pub enum SolGuardError {
    #[msg("Invalid risk level. Must be 0-3.")]
    InvalidRiskLevel,
    #[msg("Invalid event type. Must be 0-2.")]
    InvalidEventType,
}
