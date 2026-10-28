// Synthetic demo part: Precision Hydraulic Valve Spool
// CUSTOMER_DATA_USED=NO — fully synthetic, not based on any real customer design

export const DEMO_SPOOL_REQ_SET = {
  source_id: 'DEMO-SPOOL-001',
  drawing_number: 'MP-DEMO-001',
  revision: 'A',
  dimensional_requirements: [
    { requirement_id: 'D1', feature_id: 'OD_MAIN', nominal_value: 40.0,
      upper_deviation: 0.0, lower_deviation: -0.016, unit: 'mm', label: 'Main OD ⍀40 f7' },
    { requirement_id: 'D2', feature_id: 'OD_LAND', nominal_value: 38.0,
      upper_deviation: 0.0, lower_deviation: -0.011, unit: 'mm', label: 'Land OD ⍀38 h6' },
    { requirement_id: 'D3', feature_id: 'GROOVE_W', nominal_value: 6.0,
      upper_deviation: 0.015, lower_deviation: -0.015, unit: 'mm', label: 'Groove width 6 \xb10.015' },
    { requirement_id: 'D4', feature_id: 'LENGTH', nominal_value: 120.0,
      upper_deviation: 0.1, lower_deviation: -0.1, unit: 'mm', label: 'OAL 120 \xb10.1' },
  ],
  geometric_requirements: [
    { requirement_id: 'G1', feature_id: 'OD_MAIN',
      characteristic: 'CIRCULAR_RUNOUT', tolerance_value: 0.005,
      label: 'Circular runout ⌄0.005 A',
      datum_frame: { primary: { label: 'A', precedence: 1, modifier: 'NONE' } } },
    { requirement_id: 'G2', feature_id: 'PORT_HOLE',
      characteristic: 'POSITION', tolerance_value: 0.1,
      label: 'Port position ⌄0.1 A B',
      datum_frame: {
        primary: { label: 'A', precedence: 1, modifier: 'NONE' },
        secondary: { label: 'B', precedence: 2, modifier: 'NONE' },
      } },
  ],
  surface_finish_requirements: [
    { requirement_id: 'SF1', feature_id: 'OD_MAIN', ra_max: 0.4, label: 'Main OD Ra 0.4 \xb5m' },
    { requirement_id: 'SF2', feature_id: 'OD_LAND', ra_max: 0.8, label: 'Land OD Ra 0.8 \xb5m' },
  ],
  thread_requirements: [
    { requirement_id: 'T1', feature_id: 'PORT_THREAD', thread_standard: 'G1/4', label: 'Port G1/4 BSP' },
  ],
  material_requirements: [
    { requirement_id: 'MAT1', raw_designation: '42CrMo4', label: '42CrMo4 alloy steel' },
  ],
};

export const DEMO_SPOOL_META = {
  name: 'Precision Hydraulic Valve Spool',
  part_number: 'MP-DEMO-001',
  revision: 'A',
  material: '42CrMo4 alloy steel',
  note: 'Synthetic demo part — not based on any real customer design. CUSTOMER_DATA_USED=NO.',
};
