

element = 'W'
orbital = '4f'
gipaw_out = f'pseudo_demo_pbe/{element}/gipaw/ld1.out'
core_hole_out = f'pseudo_demo_pbe/{element}/{orbital}/ld1.out'
E = {'gipaw': {}, orbital: {}}
for pseudo in ['gipaw', orbital]:
    with open(f'pseudo_demo_pbe/{element}/{pseudo}/ld1.out', 'r') as f:
        lines = f.readlines()
        for line in lines:
            if 'Etot ' in line:
                E[pseudo]['Etot'] = float(line.split()[-2])
            if 'Etotps ' in line:
                E[pseudo]['Etotps'] = float(line.split()[-2])
print('Energies:', E)
E_corr = (E[orbital]['Etot'] - E[orbital]['Etotps']) - (E['gipaw']['Etot'] - E['gipaw']['Etotps'])
print(f'Correction for {element} {orbital} is {E_corr} eV')
