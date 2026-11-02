import geoh5vista as gv
import pyvista as pv

G5 = r"C:\Users\dkinakin\Downloads\Heap Leach Linework.geoh5"

model = gv.read_geoh5(G5)
model = model.combine()
model = model.elevation()
model = model.ptc('Elevation')
surface_mb = pv.MultiBlock()
# Get list of unique z-value
z_values = sorted(set(model['Elevation']))

#select adjacent lines by z-values
for i in range(len(z_values) - 1):
    lower_z = z_values[i]
    upper_z = z_values[i + 1]
    l1a = model.extract_cells(model['Elevation'] == lower_z)
    l2a = model.extract_cells(model['Elevation'] == upper_z)
    
    l1b = pv.PolyData(l1a.points, lines=l1a.cells)
    l2b = pv.PolyData(l2a.points, lines=l2a.cells)

    l1c = l1b.strip(100)
    l2c = l2b.strip(100)
   
    adjacent_lines = l1c + l2c

    # triangulate contour between adjacent lines
    if adjacent_lines.n_points > 0:
        surface = adjacent_lines.delaunay_2d()
        surface_mb.append(surface)

surface_mb.plot()
