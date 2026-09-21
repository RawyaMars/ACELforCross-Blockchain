import pm4py
from graphviz.backend.execute import ExecutableNotFound

def discover_and_save_ocdfg(ocel_json_path, output_png_path, exclude_activities=None):

    ocel = pm4py.read_ocel_json(ocel_json_path)
    if exclude_activities:
        ocel.events = ocel.events[~ocel.events["ocel:activity"].isin(exclude_activities)]




        ocel.relations = ocel.relations[~ocel.relations["ocel:activity"].isin(exclude_activities)]
    ocdfg = pm4py.discover_ocdfg(ocel)
    try:
        pm4py.save_vis_ocdfg(ocdfg, output_png_path, annotation="frequency")
    except ExecutableNotFound:





        from ocdfg_fallback_render import render_ocdfg
        render_ocdfg(ocdfg, output_png_path, annotation="frequency")
