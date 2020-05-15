"""cogeo_tiler.handler: handle request for cogeo-tiler."""

import io
import json
import os
import urllib.parse
from typing import Any, Dict, Optional, Tuple, Union

import numpy
import rasterio
from boto3.session import Session as boto3_session
from cogeo_tiler import utils
from cogeo_tiler.common import drivers, mimetype
from cogeo_tiler.ogc import wmts_template
from lambda_proxy.proxy import API
from rasterio.session import AWSSession
from rio_tiler.colormap import get_colormap
from rio_tiler.io import cogeo
from rio_tiler.profiles import img_profiles
from rio_tiler.reader import point as pointReader
from rio_tiler.utils import expression, geotiff_options, render

app = API(name="cogeo-tiler")
aws_session = AWSSession(session=boto3_session())


class TilerError(Exception):
    """Base exception class."""


route_params = dict(
    cors=True, payload_compression_method="gzip", binary_b64encode=True,
)


@app.get("/bounds", tag=["metadata"], **route_params)
def _bounds(url: str) -> Tuple[str, str, str]:
    """Handle /bounds requests."""
    with rasterio.Env(aws_session):
        return ("OK", "application/json", json.dumps(cogeo.bounds(url)))


@app.get("/metadata", tag=["metadata"], **route_params)
def _metadata(
    url: str,
    indexes: Optional[Tuple] = None,
    nodata: Optional[Union[str, int, float]] = None,
    pmin: float = 2.0,
    pmax: float = 98.0,
    max_size: int = 1024,
    histogram_bins: int = 20,
    histogram_range: Optional[str] = None,
) -> Tuple[str, str, str]:
    """Handle /metadata requests."""
    pmin = float(pmin) if isinstance(pmin, str) else pmin
    pmax = float(pmax) if isinstance(pmax, str) else pmax
    max_size = int(max_size) if isinstance(max_size, str) else max_size
    histogram_bins = (
        int(histogram_bins) if isinstance(histogram_bins, str) else histogram_bins
    )
    if isinstance(indexes, str):
        indexes = tuple(map(int, indexes.split(",")))

    if nodata is not None:
        nodata = numpy.nan if nodata == "nan" else float(nodata)

    hist_options: Dict[str, Any] = dict()
    if histogram_bins:
        hist_options.update(dict(bins=histogram_bins))
    if histogram_range:
        hist_options.update(dict(range=list(map(float, histogram_range.split(",")))))

    with rasterio.Env(aws_session):
        return (
            "OK",
            "application/json",
            json.dumps(
                cogeo.metadata(
                    url,
                    pmin,
                    pmax,
                    nodata=nodata,
                    indexes=indexes,
                    max_size=max_size,
                    hist_options=hist_options,
                )
            ),
        )


@app.get("/tilejson.json", tag=["tiles"], **route_params)
def _tilejson(
    url: str, tile_scale: int = 1, tile_format: str = None, **kwargs: Any
) -> Tuple[str, str, str]:
    """Handle /tilejson.json requests."""
    if tile_scale is not None and isinstance(tile_scale, str):
        tile_scale = int(tile_scale)

    kwargs.update(dict(url=url))
    qs = urllib.parse.urlencode(list(kwargs.items()))
    if tile_format:
        tile_url = f"{app.host}/{{z}}/{{x}}/{{y}}@{tile_scale}x.{tile_format}?{qs}"
    else:
        tile_url = f"{app.host}/{{z}}/{{x}}/{{y}}@{tile_scale}x?{qs}"

    with rasterio.Env(aws_session):
        info = cogeo.spatial_info(url)

    meta = dict(
        bounds=info["bounds"],
        center=info["center"],
        minzoom=info["minzoom"],
        maxzoom=info["maxzoom"],
        name=os.path.basename(url),
        tilejson="2.1.0",
        tiles=[tile_url],
    )
    return ("OK", "application/json", json.dumps(meta))


@app.get("/wmts", tag=["tiles"], **route_params)
@app.get("/WMTSCapabilities.xml", tag=["tiles"], **route_params)
def _wmts(
    url: str = None,
    tile_format: str = "png",
    tile_scale: int = 1,
    title: str = "Cloud Optimizied GeoTIFF",
    **kwargs: Any,
) -> Tuple[str, str, str]:
    """Handle /wmts requests."""
    if tile_scale is not None and isinstance(tile_scale, str):
        tile_scale = int(tile_scale)

    # Remove QGIS arguments
    kwargs.pop("SERVICE", None)
    kwargs.pop("REQUEST", None)

    kwargs.update(dict(url=url))
    query_string = urllib.parse.urlencode(list(kwargs.items()))

    # & is an invalid character in XML
    query_string = query_string.replace("&", "&amp;")

    with rasterio.Env(aws_session):
        info = cogeo.spatial_info(url)

    return (
        "OK",
        "application/xml",
        wmts_template(
            app.host,
            query_string,
            minzoom=info["minzoom"],
            maxzoom=info["maxzoom"],
            bounds=info["bounds"],
            tile_scale=tile_scale,
            tile_format=tile_format,
            title=title,
        ),
    )


@app.get("/<int:z>/<int:x>/<int:y>.<ext>", tag=["tiles"], **route_params)
@app.get("/<int:z>/<int:x>/<int:y>", tag=["tiles"], **route_params)
@app.get("/<int:z>/<int:x>/<int:y>@<int:scale>x.<ext>", tag=["tiles"], **route_params)
@app.get("/<int:z>/<int:x>/<int:y>@<int:scale>x", tag=["tiles"], **route_params)
def _tile(
    z: int,
    x: int,
    y: int,
    scale: int = 1,
    ext: str = None,
    url: str = None,
    indexes: Optional[Tuple] = None,
    expr: Optional[str] = None,
    nodata: Optional[Union[str, int, float]] = None,
    rescale: Optional[str] = None,
    color_formula: Optional[str] = None,
    color_map: Optional[str] = None,
    resampling_method: str = "bilinear",
) -> Tuple[str, str, bytes]:
    """Handle /tiles requests."""
    if indexes and expr:
        raise TilerError("Cannot pass indexes and expression")

    if not url:
        raise TilerError("Missing 'url' parameter")

    if nodata is not None:
        nodata = numpy.nan if nodata == "nan" else float(nodata)

    tilesize = scale * 256

    with rasterio.Env(aws_session):
        if expr is not None:
            tile, mask = expression(
                url,
                x,
                y,
                z,
                expr,
                tilesize=tilesize,
                nodata=nodata,
                resampling_method=resampling_method,
            )
        else:
            if isinstance(indexes, str):
                indexes = tuple(map(int, indexes.split(",")))
            tile, mask = cogeo.tile(
                url,
                x,
                y,
                z,
                indexes=indexes,
                tilesize=tilesize,
                nodata=nodata,
                resampling_method=resampling_method,
            )

    if not ext:
        ext = "jpg" if mask.all() else "png"

    tile = utils.postprocess(tile, mask, rescale=rescale, color_formula=color_formula)

    if color_map:
        color_map = get_colormap(color_map)

    if ext == "npy":
        sio = io.BytesIO()
        numpy.save(sio, (tile, mask))
        sio.seek(0)
        content = sio.getvalue()
    else:
        driver = drivers[ext]
        options = img_profiles.get(driver.lower(), {})
        if ext == "tif":
            options = geotiff_options(x, y, z, tilesize=tilesize)

        content = render(tile, mask, img_format=driver, colormap=color_map, **options)

    return ("OK", mimetype[ext], content)


@app.get("/point", tag=["point"], **route_params)
def _point(
    url: str, lon: float, lat: float, indexes: Optional[Tuple] = None, **kwargs,
) -> Tuple[str, str, str]:
    """Handle /point requests."""
    lon = float(lon) if isinstance(lon, str) else lon
    lat = float(lat) if isinstance(lat, str) else lat
    if isinstance(indexes, str):
        indexes = tuple(map(int, indexes.split(",")))

    with rasterio.Env(aws_session):
        with rasterio.open(url) as src_dst:
            values = pointReader(src_dst, (lon, lat), indexes=indexes, **kwargs)

    return (
        "OK",
        "application/json",
        json.dumps({"coordinates": [lon, lat], "values": values}),
    )


@app.get("/favicon.ico", cors=True, tag=["other"])
def favicon() -> Tuple[str, str, str]:
    """Favicon."""
    return ("EMPTY", "text/plain", "")
