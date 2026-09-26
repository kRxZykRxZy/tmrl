# TMNF Build Profiles

A profile is required before the native bridge can mutate TMNF.

Generate the exact game hash from Windows CMD:

    bridge\hash_tmnf.cmd

A profile is valid only when:

1. the executable SHA-256 matches exactly;
2. the profile says supported: true;
3. the required signatures/addresses pass runtime sanity checks;
4. the native adapter confirms the expected class/function behavior.

Never copy an address from a different executable build without validation.

The public-symbol research in:

    bridge/research/PUBLIC_TMNf_SYMBOL_LEADS.md

is a starting point only.
