-- Fix sequence for lab test prescriptions
SELECT setval(pg_get_serial_sequence('users_labtestprescription', 'id'),
    COALESCE((SELECT MAX(id) FROM users_labtestprescription), 0) + 1, false);

-- Fix sequence for prescriptions
SELECT setval(pg_get_serial_sequence('users_prescription', 'id'),
    COALESCE((SELECT MAX(id) FROM users_prescription), 0) + 1, false);

-- Fix sequence for prescription items
SELECT setval(pg_get_serial_sequence('users_prescriptionitem', 'id'),
    COALESCE((SELECT MAX(id) FROM users_prescriptionitem), 0) + 1, false);

-- Fix sequence for lab tests
SELECT setval(pg_get_serial_sequence('users_labtest', 'id'),
    COALESCE((SELECT MAX(id) FROM users_labtest), 0) + 1, false);

-- Fix sequence for vitals
SELECT setval(pg_get_serial_sequence('users_vitals', 'id'),
    COALESCE((SELECT MAX(id) FROM users_vitals), 0) + 1, false); 