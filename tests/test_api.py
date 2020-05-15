"""Test: cogeo-tiler API."""

import base64
import json
import os
import urllib
from io import BytesIO

import numpy
import pytest
from mock import patch

cog_path = os.path.join(os.path.dirname(__file__), "fixtures", "cog.tif")


@pytest.fixture(autouse=True)
def testing_env_var(monkeypatch):
    """Set fake env to make sure we don't hit AWS services."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "jqt")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "rde")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", "/tmp/noconfigheere")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/tmp/noconfighereeither")
    monkeypatch.setenv("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/tmp/noconfighereeither")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture()
def app():
    """Make sure we use mocked env."""
    from cogeo_tiler.handler import app

    return app


@pytest.fixture()
def event():
    """Event fixture."""
    return {
        "resource": "/",
        "path": "/",
        "httpMethod": "GET",
        "headers": {"Host": "somewhere-over-the-rainbow.com"},
        "queryStringParameters": {},
    }


def test_API_favicon(app, event):
    """Test /favicon.ico route."""
    event["path"] = "/favicon.ico"

    resp = {
        "body": "",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 204,
    }
    res = app(event, {})
    assert res == resp


def test_API_tilejson(app, event):
    """Test /tilejson.json route."""
    from cogeo_tiler.handler import app

    urlqs = urllib.parse.urlencode([("url", cog_path)])

    event["path"] = f"/tilejson.json"
    res = app(event, {})
    assert res["statusCode"] == 500
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert "url" in body["errorMessage"]

    event["path"] = f"/tilejson.json"
    event["queryStringParameters"] = {"url": cog_path, "tile_scale": "2"}
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert body["name"] == "cog.tif"
    assert body["tilejson"] == "2.1.0"
    assert body["tiles"][0] == (
        f"https://somewhere-over-the-rainbow.com/{{z}}/{{x}}/{{y}}@2x?{urlqs}"
    )
    assert len(body["bounds"]) == 4
    assert len(body["center"]) == 3
    assert body["minzoom"] == 6
    assert body["maxzoom"] == 8

    # test with tile_format
    event["path"] = f"/tilejson.json"
    event["queryStringParameters"] = {"url": cog_path, "tile_format": "jpg"}
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert body["tiles"][0] == (
        f"https://somewhere-over-the-rainbow.com/{{z}}/{{x}}/{{y}}@1x.jpg?{urlqs}"
    )

    # test with kwargs
    event["path"] = f"/tilejson.json"
    event["queryStringParameters"] = {"url": cog_path, "rescale": "-1,1"}
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert body["tiles"][0] == (
        f"https://somewhere-over-the-rainbow.com/{{z}}/{{x}}/{{y}}@1x?rescale=-1%2C1&{urlqs}"
    )


def test_API_bounds(app, event):
    """Test /bounds route."""
    from cogeo_tiler.handler import app

    event["path"] = f"/bounds"
    res = app(event, {})
    assert res["statusCode"] == 500
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert "url" in body["errorMessage"]

    event["path"] = f"/bounds"
    event["queryStringParameters"] = {"url": cog_path}
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert body["address"]
    assert len(body["bounds"]) == 4


def test_API_metadata(app, event):
    """Test /metadata route."""
    from cogeo_tiler.handler import app

    event["path"] = f"/metadata"
    res = app(event, {})
    assert res["statusCode"] == 500
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert "url" in body["errorMessage"]

    event["path"] = f"/metadata"
    event["queryStringParameters"] = {"url": cog_path}
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert body["address"]
    assert len(body["statistics"].keys()) == 1
    assert len(body["statistics"]["1"]["histogram"][0]) == 20
    assert body["band_descriptions"]

    event["path"] = f"/metadata"
    event["queryStringParameters"] = {"url": cog_path, "histogram_bins": "10"}
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert len(body["statistics"]["1"]["histogram"][0]) == 10

    event["queryStringParameters"] = {
        "url": cog_path,
        "pmin": "5",
        "pmax": "95",
        "nodata": "-9999",
        "indexes": "1",
        "histogram_range": "1,1000",
    }
    res = app(event, {})

    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert len(body["statistics"].keys()) == 1


def test_API_wmts(app, event):
    """Test /wmts route."""
    from cogeo_tiler.handler import app

    event["path"] = f"/wmts"
    event["queryStringParameters"] = {"url": cog_path}
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/xml"
    assert res["body"]
    assert "https://somewhere-over-the-rainbow.com/wmts?url" in res["body"]

    event["queryStringParameters"] = {"url": cog_path, "tile_scale": "2"}
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/xml"
    assert res["body"]
    assert (
        "https://somewhere-over-the-rainbow.com/{TileMatrix}/{TileCol}/{TileRow}@2x.png?url"
        in res["body"]
    )


def test_API_point(app, event):
    """Test /point route."""
    from cogeo_tiler.handler import app

    event["path"] = f"/point"
    event["queryStringParameters"] = {
        "url": cog_path,
        "lon": "-2.0",
        "lat": "49.0",
    }
    res = app(event, {})
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["values"] == [-3]
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"

    event["queryStringParameters"] = {
        "url": cog_path,
        "lon": "-2.0",
        "lat": "49.0",
        "indexes": "1,1,1",
    }
    res = app(event, {})
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    body["values"] == [-3, -3, -3]
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"

    event["queryStringParameters"] = {
        "url": cog_path,
        "lon": "-2.0",
        "lat": "53.0",
    }
    res = app(event, {})
    assert res["statusCode"] == 500
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert body["errorMessage"] == "Point is outside dataset bounds"


def test_API_tiles(app, event):
    """Test /tiles route."""
    from cogeo_tiler.handler import app

    # test missing url in queryString
    event["path"] = f"/7/62/44.jpg"
    res = app(event, {})
    assert res["statusCode"] == 500
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert body["errorMessage"] == "Missing 'url' parameter"

    # test missing expr and indexes in queryString
    event["path"] = f"/7/62/44.jpg"
    event["queryStringParameters"] = {"url": cog_path, "indexes": "1", "expr": "b1/b1"}
    res = app(event, {})
    assert res["statusCode"] == 500
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert body["errorMessage"] == "Cannot pass indexes and expression"

    # test valid request with linear rescaling
    event["path"] = f"/7/62/44.png"
    event["queryStringParameters"] = {
        "url": cog_path,
        "rescale": "0,10000",
        "color_formula": "Gamma R 3.0",
    }
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]
    assert res["isBase64Encoded"]

    # test valid request with expression
    event["path"] = f"/7/62/44.png"
    event["queryStringParameters"] = {
        "url": cog_path,
        "expr": "b1/b1",
        "rescale": "0,1",
    }
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]
    assert res["isBase64Encoded"]

    # test valid jpg request with linear rescaling
    event["path"] = f"/7/62/44.jpg"
    event["queryStringParameters"] = {
        "url": cog_path,
        "rescale": "0,10000",
        "indexes": "1",
        "nodata": "-9999",
    }
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/jpg"
    assert res["body"]
    assert res["isBase64Encoded"]

    # test valid jpg request with rescaling and colormap
    event["path"] = f"/7/62/44.png"
    event["queryStringParameters"] = {
        "url": cog_path,
        "rescale": "0,10000",
        "color_map": "schwarzwald",
    }
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]
    assert res["isBase64Encoded"]

    # test scale (512px tile size)
    event["path"] = f"/7/62/44@2x.png"
    event["queryStringParameters"] = {"url": cog_path, "rescale": "0,10000"}
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]
    assert res["isBase64Encoded"]

    # test no ext (partial: png)
    event["path"] = f"/7/62/44"
    event["queryStringParameters"] = {"url": cog_path, "rescale": "0,10000"}
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]
    assert res["isBase64Encoded"]

    # test no ext (full: jpeg)
    event["path"] = f"/8/126/87"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = {"url": cog_path, "rescale": "0,10000"}
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/jpg"
    assert res["body"]
    assert res["isBase64Encoded"]

    # test tif
    event["path"] = f"/8/126/87.tif"
    event["queryStringParameters"] = {"url": cog_path}
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["body"]
    assert res["isBase64Encoded"]
    headers = res["headers"]
    assert headers["Content-Type"] == "image/tiff"

    # test npy
    event["path"] = f"/8/126/87.npy"
    event["queryStringParameters"] = {"url": cog_path}
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["isBase64Encoded"]
    headers = res["headers"]
    assert headers["Content-Type"] == "application/x-binary"
    body = base64.b64decode(res["body"])
    data, datamask = numpy.load(BytesIO(body), allow_pickle=True)
    assert data.shape == (1, 256, 256)
    assert datamask.shape == (256, 256)


@patch("cogeo_tiler.handler.cogeo.tile")
def test_API_tilesMock(tiler, app, event):
    """Tests if route pass the right variables."""
    from cogeo_tiler.handler import app

    tilesize = 256
    tile = numpy.random.rand(3, tilesize, tilesize).astype(numpy.int16)
    mask = numpy.full((tilesize, tilesize), 255)
    mask[0:100, 0:100] = 0

    tiler.return_value = (tile, mask)

    # test no ext
    event["path"] = f"/8/126/87"
    event["queryStringParameters"] = {"url": cog_path, "rescale": "0,10000"}
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["body"]
    assert res["isBase64Encoded"]
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    kwargs = tiler.call_args[1]
    assert kwargs["tilesize"] == 256
    vars = tiler.call_args[0]
    assert vars[1] == 126
    assert vars[2] == 87
    assert vars[3] == 8
