// Synthesizes a short code from a name — used only for dev/mock-mode fixture
// data, which predates codes existing on real opt_master rows and doesn't
// carry ea_code/reg_code fields. Must stay identical everywhere it's used
// (OperatorsTab.jsx's dev operator list, OverviewTab.jsx's dev EA/Registrar
// distribution) so a code generated in one place matches the same name's
// code generated in another — e.g. clicking an EA bar on the Overview page
// needs to produce the same code OperatorsTab's dev fixture already tagged
// that EA's operators with, or the resulting filter matches nothing.
export const codeOf = (name) => (name || '').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 6);
