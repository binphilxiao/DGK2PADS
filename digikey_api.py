# -*- coding: utf-8 -*-
"""
DigiKey API V4 客户端
通过 DigiKey API 直接搜索和获取元件信息

API 文档: https://developer.digikey.com/products/product-information-v4

需要:
1. 在 https://developer.digikey.com 注册开发者账号
2. 创建应用，获取 Client ID 和 Client Secret
3. 订阅 Product Information V4 API
"""

import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
import ssl
import threading
import webbrowser
import http.server
import secrets
from digikey_parser import Component
from config import PACKAGE_NORMALIZE, CATEGORY_PREFIXES

# ============================================================
# DigiKey 常用类别 ID（固定值，不会变化）
# ============================================================
DIGIKEY_CATEGORIES = {
    "Chip Resistor - Surface Mount": 52,
    "Through Hole Resistors": 53,
    "Resistor Networks/Arrays": 56,
    "Ceramic Capacitors": 60,
    "Aluminum Electrolytic Capacitors": 58,
    "Tantalum Capacitors": 72,
    "Film Capacitors": 63,
    "Fixed Inductors": 71,
    "Ferrite Beads": 941,
    "TVS Diodes": 986,
    "Schottky Diodes": 978,
    "Rectifiers": 976,
    "Zener Diodes": 987,
    "LEDs": 19,
    "MOSFETs": 68,
    "BJTs": 67,
    "Voltage Regulators - Linear": 694,
    "Voltage Regulators - Switching": 695,
    "Op Amps": 687,
    "Microcontrollers": 801,
    "Connectors": 16,
    "Crystals": 73,
    "Oscillators": 74,
}

# 电阻/电容/电感常用参数 ID（DigiKey 参数 ID）
# 这些 ID 可通过 KeywordSearch 响应中的 FilterOptions 获取
COMMON_PARAMETER_IDS = {
    # 电阻
    "resistance": 2085,          # 阻值
    "power_rating": 2,           # 功率 (Power (Watts))
    "tolerance_res": 3,          # 容差
    "temperature_coeff": 17,     # 温度系数

    # 电容
    "capacitance": 2049,         # 容值
    "voltage_cap": 2079,         # 额定电压
    "temperature_char": 2052,    # 温度特性 (X7R, X5R, C0G, etc.)
    "tolerance_cap": 3,          # 容差

    # 电感
    "inductance": 2088,          # 感值
    "current_rating": 2094,      # 额定电流
    "dcr": 2090,                 # 直流电阻

    # 通用
    "package": 16,               # 封装/外壳
    "mounting_type": 69,         # 安装类型
    "operating_temp": 252,       # 工作温度范围
    "status": 1,                 # 状态（Active, etc.）
}

# Common manufacturers for dropdown filter
COMMON_MANUFACTURERS = [
    "", "Yageo", "Samsung Electro-Mechanics", "Murata", "TDK",
    "Vishay", "Panasonic", "KEMET", "Wurth Elektronik", "Bourns",
    "TE Connectivity", "Rohm", "KOA Speer", "Stackpole",
    "Texas Instruments", "STMicroelectronics", "NXP", "Microchip",
    "ON Semiconductor", "Infineon", "Analog Devices", "Nexperia",
    "Diodes Incorporated", "Littelfuse", "Taiyo Yuden",
]

# Common resistor series for dropdown
COMMON_RESISTOR_SERIES = [
    "", "RC_L", "RT_L", "AC", "AA", "AT",
    "ERJ", "CRCW", "MCR", "RK73H", "RK73B",
    "CR", "RMCF", "RC", "RR", "RG",
    "TNPW", "WSL",
]

# Resistor search preset
RESISTOR_SEARCH_CONFIG = {
    "category_name": "Chip Resistor - Surface Mount",
    "category_id": 52,
    "keyword": "resistor",
    "split_param_id": 2085,  # Resistance - segment by value when > 300
    "parameters": [
        {"name": "Resistance", "key": "resistance", "param_id": 2085,
         "values": ["", "1", "10", "100", "1k", "4.7k", "10k",
                    "47k", "100k", "1M"]},
        {"name": "Package", "key": "package", "param_id": 16,
         "values": ["", "01005", "0201", "0402", "0603", "0805",
                    "1206", "1210", "2010", "2512"]},
        {"name": "Power Rating", "key": "power_rating", "param_id": 2,
         "values": ["", "1/32W", "1/20W", "1/16W", "1/10W",
                    "1/8W", "1/4W", "1/2W", "1W", "2W"]},
        {"name": "Tolerance", "key": "tolerance", "param_id": 3,
         "values": ["", "±0.1%", "±0.25%", "±0.5%", "±1%", "±2%", "±5%", "±10%"]},
        {"name": "Temp Coefficient", "key": "temp_coeff", "param_id": 17,
         "values": ["", "10ppm/C", "25ppm/C", "50ppm/C",
                    "100ppm/C", "200ppm/C"]},
    ],
}

CAPACITOR_SEARCH_CONFIG = {
    "category_name": "Ceramic Capacitors",
    "category_id": 60,
    "keyword": "capacitor ceramic",
    "split_param_id": 2049,  # Capacitance - segment by value when > 300
    "parameters": [
        {"name": "Capacitance", "key": "capacitance", "param_id": 2049,
         "values": ["", "10pF", "100pF", "1nF", "10nF", "100nF",
                    "1uF", "4.7uF", "10uF", "22uF", "100uF"]},
        {"name": "Package", "key": "package", "param_id": 16,
         "values": ["", "01005", "0201", "0402", "0603", "0805",
                    "1206", "1210", "1812", "2220"]},
        {"name": "Voltage Rating", "key": "voltage", "param_id": 2079,
         "values": ["", "4V", "6.3V", "10V", "16V", "25V",
                    "50V", "100V", "200V"]},
        {"name": "Temp Characteristic", "key": "temp_char", "param_id": 2052,
         "values": ["", "C0G/NP0", "X5R", "X7R", "X6S", "X7S", "Y5V"]},
        {"name": "Tolerance", "key": "tolerance", "param_id": 3,
         "values": ["", "1%", "2%", "5%", "10%", "20%"]},
    ],
}

INDUCTOR_SEARCH_CONFIG = {
    "category_name": "Fixed Inductors",
    "category_id": 71,
    "keyword": "inductor",
    "split_param_id": 2088,  # Inductance - segment by value when > 300
    "parameters": [
        {"name": "Inductance", "key": "inductance", "param_id": 2088,
         "values": ["", "1nH", "10nH", "100nH", "1uH", "4.7uH",
                    "10uH", "47uH", "100uH", "1mH"]},
        {"name": "Package", "key": "package", "param_id": 16,
         "values": ["", "0201", "0402", "0603", "0805",
                    "1008", "1210", "1812"]},
        {"name": "Current Rating", "key": "current", "param_id": 2094,
         "values": ["", "0.1A", "0.2A", "0.5A", "1A",
                    "1.5A", "2A", "3A", "5A", "10A"]},
        {"name": "DCR", "key": "dcr", "param_id": 2090,
         "values": ["", "10mOhm", "50mOhm", "100mOhm",
                    "200mOhm", "500mOhm", "1Ohm"]},
    ],
}

# All search preset configurations
SEARCH_PRESETS = {
    "Chip Resistor": RESISTOR_SEARCH_CONFIG,
    "MLCC Capacitor": CAPACITOR_SEARCH_CONFIG,
    "Inductor": INDUCTOR_SEARCH_CONFIG,
}


class DigiKeyAPIError(Exception):
    """DigiKey API 错误"""
    pass


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """处理 OAuth 回调的本地 HTTP 服务器"""

    auth_code = None
    auth_state = None
    error = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if 'code' in params:
            _OAuthCallbackHandler.auth_code = params['code'][0]
            _OAuthCallbackHandler.auth_state = params.get('state', [None])[0]
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(
                '<html><body style="text-align:center;padding:50px;font-family:sans-serif">'
                '<h2>\u2705 DigiKey \u6388\u6743\u6210\u529f!</h2>'
                '<p>\u8bf7\u8fd4\u56de\u7a0b\u5e8f\u7ee7\u7eed\u64cd\u4f5c\u3002\u6b64\u7a97\u53e3\u53ef\u4ee5\u5173\u95ed\u3002</p>'
                '</body></html>'.encode('utf-8'))
        elif 'error' in params:
            _OAuthCallbackHandler.error = params.get('error_description',
                                                     params['error'])[0]
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(
                f'<html><body style="text-align:center;padding:50px;font-family:sans-serif">'
                f'<h2>\u274c \u6388\u6743\u5931\u8d25</h2>'
                f'<p>{_OAuthCallbackHandler.error}</p>'
                f'</body></html>'.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # 静默日志


class DigiKeyClient:
    """DigiKey API V4 客户端 (OAuth 2.0 Authorization Code 流程)"""

    # API 端点
    SANDBOX_BASE = "https://sandbox-api.digikey.com"
    PRODUCTION_BASE = "https://api.digikey.com"

    # OAuth 端点
    SANDBOX_AUTH_URL = "https://sandbox-api.digikey.com/v1/oauth2/authorize"
    PRODUCTION_AUTH_URL = "https://api.digikey.com/v1/oauth2/authorize"
    SANDBOX_TOKEN_URL = "https://sandbox-api.digikey.com/v1/oauth2/token"
    PRODUCTION_TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"

    SEARCH_PATH = "/products/v4/search/keyword"
    DETAIL_PATH = "/products/v4/search"
    CATEGORIES_PATH = "/products/v4/search/categories"

    CALLBACK_PORT = 8139
    REDIRECT_URI = f"https://localhost:{CALLBACK_PORT}/callback"

    def __init__(self, client_id, client_secret, use_sandbox=False):
        self.client_id = client_id
        self.client_secret = client_secret
        self.use_sandbox = use_sandbox
        self.base_url = self.SANDBOX_BASE if use_sandbox else self.PRODUCTION_BASE
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = 0

        # SSL context
        self._ssl_ctx = ssl.create_default_context()

        # 加载已保存的 token
        self._load_tokens()

    def _get_auth_url(self):
        return self.SANDBOX_AUTH_URL if self.use_sandbox else self.PRODUCTION_AUTH_URL

    def _get_token_url(self):
        return self.SANDBOX_TOKEN_URL if self.use_sandbox else self.PRODUCTION_TOKEN_URL

    def _token_cache_file(self):
        mode = "sandbox" if self.use_sandbox else "production"
        return os.path.join(os.path.expanduser("~"),
                            f".digikey_token_{mode}.json")

    def _save_tokens(self):
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expires_at": self.token_expires_at,
            "client_id": self.client_id,
        }
        with open(self._token_cache_file(), 'w') as f:
            json.dump(data, f)

    def _load_tokens(self):
        cache_file = self._token_cache_file()
        if os.path.isfile(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                if data.get("client_id") == self.client_id:
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    self.token_expires_at = data.get("token_expires_at", 0)
            except (json.JSONDecodeError, IOError):
                pass

    def _make_request(self, url, method="GET", data=None, headers=None,
                      timeout=30):
        """发送 HTTP 请求"""
        if headers is None:
            headers = {}

        if data is not None and isinstance(data, (dict, list)):
            data = json.dumps(data).encode('utf-8')
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'
        elif data is not None and isinstance(data, str):
            data = data.encode('utf-8')

        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout,
                                        context=self._ssl_ctx) as resp:
                body = resp.read().decode('utf-8')
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            raise DigiKeyAPIError(
                f"HTTP {e.code}: {e.reason}\n{body}"
            )
        except urllib.error.URLError as e:
            raise DigiKeyAPIError(f"网络错误: {e.reason}")

    def authenticate_browser(self):
        """
        OAuth 2.0 Authorization Code 流程
        1. 打开浏览器让用户登录 DigiKey
        2. 用户授权后重定向到本地回调
        3. 获取 authorization code 并换取 access token
        """
        state = secrets.token_urlsafe(16)

        # 构建授权 URL
        auth_params = urllib.parse.urlencode({
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.REDIRECT_URI,
            'state': state,
        })
        auth_url = self._get_auth_url() + "?" + auth_params

        # 重置回调处理器状态
        _OAuthCallbackHandler.auth_code = None
        _OAuthCallbackHandler.auth_state = None
        _OAuthCallbackHandler.error = None

        # 创建本地 HTTPS 服务器等待回调
        # DigiKey 要求 https redirect，使用自签名证书或 http
        # 实际上 DigiKey 允许 localhost 使用 http
        redirect_uri_http = f"http://localhost:{self.CALLBACK_PORT}/callback"

        # 重新构建使用 http 的授权 URL
        auth_params = urllib.parse.urlencode({
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': redirect_uri_http,
            'state': state,
        })
        auth_url = self._get_auth_url() + "?" + auth_params

        server = http.server.HTTPServer(
            ('localhost', self.CALLBACK_PORT), _OAuthCallbackHandler)
        server.timeout = 120  # 2 分钟超时

        # 打开浏览器
        webbrowser.open(auth_url)

        # 等待回调 (阻塞)
        server.handle_request()
        server.server_close()

        if _OAuthCallbackHandler.error:
            raise DigiKeyAPIError(
                f"DigiKey 授权失败: {_OAuthCallbackHandler.error}")

        auth_code = _OAuthCallbackHandler.auth_code
        if not auth_code:
            raise DigiKeyAPIError("未收到授权码，用户可能取消了授权或超时")

        if _OAuthCallbackHandler.auth_state != state:
            raise DigiKeyAPIError("OAuth state 不匹配，可能存在安全问题")

        # 用授权码换取 token
        self._exchange_code(auth_code, redirect_uri_http)
        return True

    def _exchange_code(self, auth_code, redirect_uri):
        """用授权码换取 access token"""
        token_url = self._get_token_url()

        post_data = urllib.parse.urlencode({
            'grant_type': 'authorization_code',
            'code': auth_code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': redirect_uri,
        })

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        result = self._make_request(token_url, method="POST",
                                     data=post_data, headers=headers)

        self.access_token = result.get('access_token')
        self.refresh_token = result.get('refresh_token')
        expires_in = result.get('expires_in', 3600)
        self.token_expires_at = time.time() + expires_in - 60

        if not self.access_token:
            raise DigiKeyAPIError(
                f"获取访问令牌失败。响应: {result}")

        self._save_tokens()

    def _refresh_access_token(self):
        """使用 refresh_token 刷新 access_token"""
        if not self.refresh_token:
            raise DigiKeyAPIError("没有 refresh token，请重新登录授权")

        token_url = self._get_token_url()

        post_data = urllib.parse.urlencode({
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        })

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        try:
            result = self._make_request(token_url, method="POST",
                                         data=post_data, headers=headers)
        except DigiKeyAPIError:
            # refresh token 可能已过期，需要重新授权
            raise DigiKeyAPIError("Token 已过期，请重新点击'登录 DigiKey'授权")

        self.access_token = result.get('access_token')
        new_refresh = result.get('refresh_token')
        if new_refresh:
            self.refresh_token = new_refresh
        expires_in = result.get('expires_in', 3600)
        self.token_expires_at = time.time() + expires_in - 60

        if not self.access_token:
            raise DigiKeyAPIError("刷新令牌失败，请重新登录授权")

        self._save_tokens()

    def authenticate(self):
        """
        确保有有效的 access token
        如果有 refresh_token 就用它刷新，否则需要浏览器授权
        """
        if self.access_token and time.time() < self.token_expires_at:
            return True  # token 仍然有效

        if self.refresh_token:
            try:
                self._refresh_access_token()
                return True
            except DigiKeyAPIError:
                pass  # refresh 失败，需要重新授权

        # 需要浏览器授权
        return self.authenticate_browser()

    def _ensure_auth(self):
        """确保已认证"""
        if not self.access_token or time.time() >= self.token_expires_at:
            if self.refresh_token:
                self._refresh_access_token()
            else:
                raise DigiKeyAPIError(
                    "未登录。请先点击'登录 DigiKey'进行授权。")

    def _api_headers(self):
        """生成 API 请求头"""
        self._ensure_auth()
        return {
            'Authorization': f'Bearer {self.access_token}',
            'X-DIGIKEY-Client-Id': self.client_id,
            'Content-Type': 'application/json',
            'X-DIGIKEY-Locale-Language': 'en',
            'X-DIGIKEY-Locale-Currency': 'USD',
            'X-DIGIKEY-Locale-Site': 'US',
        }

    def search_keyword(self, keywords, limit=50, offset=0,
                       category_id=None, manufacturer_ids=None,
                       parameter_filters=None,
                       exclude_marketplace=True):
        """
        关键字搜索

        Args:
            keywords: 搜索关键字
            limit: 返回结果数量 (最大50)
            offset: 偏移量（翻页）
            category_id: 类别 ID
            manufacturer_ids: 制造商 ID 列表
            parameter_filters: 参数过滤器列表
                [{"ParameterId": int, "ValueId": str}, ...]
            exclude_marketplace: 是否排除市场卖家

        Returns:
            dict: API 响应
        """
        url = self.base_url + self.SEARCH_PATH

        body = {
            "Keywords": keywords,
            "Limit": min(limit, 50),
            "Offset": offset,
            "ExcludeMarketPlaceProducts": exclude_marketplace,
        }

        # 构建过滤器
        filter_opts = {}

        if category_id:
            filter_opts["CategoryFilter"] = [{"Id": str(category_id)}]

        if manufacturer_ids:
            filter_opts["ManufacturerFilter"] = [
                {"Id": mid} for mid in manufacturer_ids
            ]

        # 参数过滤器 (V4 API 格式)
        if parameter_filters and category_id:
            filter_opts["ParameterFilterRequest"] = {
                "CategoryFilter": {"Id": str(category_id)},
                "ParameterFilters": parameter_filters,
            }

        if filter_opts:
            body["FilterOptionsRequest"] = filter_opts

        result = self._make_request(url, method="POST", data=body,
                                     headers=self._api_headers())
        return result

    def search_all(self, keywords, category_id=None,
                   manufacturer_ids=None, parameter_filters=None,
                   progress_callback=None, stop_flag=None):
        """
        搜索并获取所有结果（自动翻页）

        DigiKey API 限制 Offset + Limit <= 300，因此单次搜索最多 300 条。

        Args:
            keywords: 搜索关键字
            category_id, manufacturer_ids, parameter_filters: 过滤条件
            progress_callback: 进度回调 fn(current, total)

        Returns:
            list[dict]: 所有产品列表
        """
        API_MAX_OFFSET = 300  # DigiKey hard limit: Offset + Limit <= 300
        all_products = []
        offset = 0
        total = None
        page_size = 50

        while True:
            if stop_flag and stop_flag.is_set():
                break
            # Ensure we don't exceed API limit
            if offset + page_size > API_MAX_OFFSET:
                remaining = API_MAX_OFFSET - offset
                if remaining <= 0:
                    break
                page_size = remaining

            result = self.search_keyword(
                keywords, limit=page_size, offset=offset,
                category_id=category_id,
                manufacturer_ids=manufacturer_ids,
                parameter_filters=parameter_filters,
            )

            products = result.get("Products", [])
            if total is None:
                total = result.get("ProductsCount", len(products))

            all_products.extend(products)

            if progress_callback and total:
                progress_callback(len(all_products),
                                  min(total, API_MAX_OFFSET))

            offset += len(products)

            if len(products) < page_size:
                break

            if total and offset >= total:
                break

            if offset >= API_MAX_OFFSET:
                break

            # 遵守速率限制
            time.sleep(0.5)

        return all_products

    def search_all_segmented(self, keywords, category_id=None,
                              manufacturer_ids=None,
                              parameter_filters=None,
                              split_param_id=None,
                              split_value_ids=None,
                              progress_callback=None,
                              segment_callback=None,
                              stop_flag=None):
        """
        获取所有结果，当总数超过 300 时自动按 split 参数分段获取。

        Args:
            keywords, category_id, manufacturer_ids, parameter_filters:
                与 search_all 相同
            split_param_id: 用于分段的参数 ID（如 2085=阻值）
            split_value_ids: 该参数所有可用的 ValueId 列表
            progress_callback: fn(fetched, estimated_total, message)
            segment_callback: fn(new_products) - 每完成一个分段就回调

        Returns:
            tuple: (all_products, total_estimated)
        """
        API_MAX = 300
        base_filters = parameter_filters or []

        # 如果没有分段参数，直接普通搜索
        if not split_param_id or not split_value_ids:
            products = self.search_all(
                keywords, category_id=category_id,
                manufacturer_ids=manufacturer_ids,
                parameter_filters=base_filters or None,
                progress_callback=lambda c, t:
                    progress_callback(c, t, "") if progress_callback else None,
                stop_flag=stop_flag,
            )
            if segment_callback and products:
                segment_callback(products)
            return products, len(products)

        # 先探测不带分段参数时的总数
        probe = self.search_keyword(
            keywords, limit=1, category_id=category_id,
            manufacturer_ids=manufacturer_ids,
            parameter_filters=base_filters or None,
        )
        total_est = probe.get("ProductsCount", 0)

        if total_est <= API_MAX:
            # 不需要分段
            products = self.search_all(
                keywords, category_id=category_id,
                manufacturer_ids=manufacturer_ids,
                parameter_filters=base_filters or None,
                progress_callback=lambda c, t:
                    progress_callback(c, t, "") if progress_callback else None,
                stop_flag=stop_flag,
            )
            if segment_callback and products:
                segment_callback(products)
            return products, total_est

        # 需要分段获取
        all_products = []
        segments_done = [0]
        segments_total = [0]

        def _fetch_segment(value_ids, depth=0):
            """递归获取一个分段的结果"""
            if not value_ids:
                return
            if stop_flag and stop_flag.is_set():
                return

            # 构建含分段参数的过滤器
            seg_filters = list(base_filters)
            seg_filters.append({
                "ParameterId": split_param_id,
                "FilterValues": [{"Id": vid} for vid in value_ids],
            })

            # 探测此分段的数量
            probe = self.search_keyword(
                keywords, limit=1, category_id=category_id,
                manufacturer_ids=manufacturer_ids,
                parameter_filters=seg_filters,
            )
            seg_total = probe.get("ProductsCount", 0)

            if seg_total == 0:
                segments_done[0] += 1
                if progress_callback:
                    progress_callback(
                        len(all_products), total_est,
                        f"Segment {segments_done[0]}/{segments_total[0]}: "
                        f"empty, skipped")
                return

            if seg_total <= API_MAX or len(value_ids) <= 1:
                # 可以完整获取（或无法再拆分）
                products = self.search_all(
                    keywords, category_id=category_id,
                    manufacturer_ids=manufacturer_ids,
                    parameter_filters=seg_filters,
                    stop_flag=stop_flag,
                )
                all_products.extend(products)
                segments_done[0] += 1
                if progress_callback:
                    progress_callback(
                        len(all_products), total_est,
                        f"Segment {segments_done[0]}/{segments_total[0]}: "
                        f"+{len(products)}")
                # 每个分段完成后立即回调，送出新数据
                if segment_callback and products:
                    segment_callback(products)
                time.sleep(0.3)
                return

            # 分段仍然超过 300，二分递归
            segments_total[0] += 1  # 拆分产生额外段
            mid = len(value_ids) // 2
            if progress_callback:
                progress_callback(
                    len(all_products), total_est,
                    f"Segment too large ({seg_total}), splitting...")
            _fetch_segment(value_ids[:mid], depth + 1)
            _fetch_segment(value_ids[mid:], depth + 1)

        # 初始切分：估算需要多少段
        num_initial = max(2, (total_est + API_MAX - 1) // API_MAX)
        batch_size = max(1, len(split_value_ids) // num_initial)
        initial_batches = []
        for i in range(0, len(split_value_ids), batch_size):
            initial_batches.append(split_value_ids[i:i + batch_size])

        segments_total[0] = len(initial_batches)

        if progress_callback:
            progress_callback(
                0, total_est,
                f"~{total_est} results, splitting into "
                f"~{len(initial_batches)} segments...")

        for batch in initial_batches:
            if stop_flag and stop_flag.is_set():
                break
            _fetch_segment(batch)

        return all_products, total_est

    def get_categories(self):
        """获取所有类别"""
        url = self.base_url + self.CATEGORIES_PATH
        return self._make_request(url, headers=self._api_headers())

    def get_product_details(self, digikey_pn):
        """获取单个产品详细信息"""
        url = self.base_url + self.DETAIL_PATH + "/" + urllib.parse.quote(
            digikey_pn, safe='')
        return self._make_request(url, headers=self._api_headers())

    def get_filter_options(self, keywords, category_id=None):
        """
        获取搜索结果的可用过滤选项

        先执行一次搜索，从响应中提取 FilterOptions
        """
        result = self.search_keyword(keywords, limit=1,
                                      category_id=category_id)
        return result

    def discover_filter_ids(self, keywords, category_id=None):
        """
        预搜索以获取可用的过滤选项 ID（制造商 ID、参数值 ID）。

        Returns:
            tuple: (manufacturer_map, param_value_map, total_count)
                manufacturer_map: {name_lower: id}
                param_value_map: {param_id: {value_text_lower: value_id}}
                total_count: 总匹配数
        """
        result = self.search_keyword(keywords, limit=1,
                                      category_id=category_id)
        total_count = result.get("ProductsCount", 0)
        filter_options = result.get("FilterOptions", {})

        # 解析制造商列表
        # V4 API 格式: {"Id": 13, "Value": "YAGEO", "ProductCount": ...}
        manufacturer_map = {}
        mfr_list = filter_options.get("Manufacturers", [])
        for mfr in mfr_list:
            name = mfr.get("Value", "")
            mid = mfr.get("Id")
            if name and mid is not None:
                manufacturer_map[name.lower()] = mid

        # 解析参数过滤选项
        # V4 API 格式: [{"ParameterId": 3, "ParameterName": "Tolerance",
        #   "FilterValues": [{"ValueId": "1131", "ValueName": "±1%"}, ...]}]
        param_value_map = {}
        param_section = filter_options.get("ParametricFilters", [])

        for pf in param_section:
            param_id = pf.get("ParameterId")
            values = pf.get("FilterValues", [])
            value_map = {}
            for v in values:
                vname = v.get("ValueName", "")
                vid = v.get("ValueId")
                if vname and vid is not None:
                    value_map[vname.lower()] = str(vid)
            if param_id is not None and value_map:
                param_value_map[int(param_id)] = value_map

        return manufacturer_map, param_value_map, total_count


def api_product_to_component(product):
    """
    将 DigiKey API 产品数据转换为 Component 对象

    Args:
        product: DigiKey API 返回的产品字典

    Returns:
        Component
    """
    comp = Component()

    # 基本信息
    desc = product.get("Description", {})
    comp.description = desc.get("ProductDescription", "")

    mfr = product.get("Manufacturer", {})
    comp.manufacturer = mfr.get("Name", "")
    comp.mfr_pn = product.get("ManufacturerProductNumber", "")

    # Series
    series_info = product.get("Series", {})
    if isinstance(series_info, dict):
        comp.series = series_info.get("Name", "")
    elif isinstance(series_info, str):
        comp.series = series_info

    # DigiKey 料号（取第一个变体）
    variations = product.get("ProductVariations", [])
    if variations:
        comp.digikey_pn = variations[0].get("DigiKeyProductNumber", "")

    # 参数
    parameters = product.get("Parameters", [])
    for param in parameters:
        param_id = param.get("ParameterId", 0)
        param_value = param.get("ValueText", "") or param.get("Value", "")
        param_name = param.get("ParameterText", "").lower()

        if param_id == 16 or "package" in param_name:
            comp.package_raw = param_value
        elif param_id == 69 or "mounting" in param_name:
            comp.mounting_type = param_value
        elif "resistance" in param_name and not comp.value:
            comp.value = param_value
        elif "capacitance" in param_name and not comp.value:
            comp.value = param_value
        elif "inductance" in param_name and not comp.value:
            comp.value = param_value
        elif "tolerance" in param_name and not comp.tolerance:
            comp.tolerance = param_value
        elif param_id == 2 or ("power" in param_name and "watt" in param_name):
            if not comp.power_rating:
                comp.power_rating = param_value
        elif param_id == 17 or "temperature coefficient" in param_name:
            if not comp.temp_coeff:
                comp.temp_coeff = param_value
        elif param_id == 252 or "operating temperature" in param_name:
            if not comp.operating_temp:
                comp.operating_temp = param_value
        elif "voltage" in param_name and not comp.voltage_rating:
            comp.voltage_rating = param_value

    # 类别
    cat = product.get("Category", {})
    comp.category = cat.get("Name", "")

    # 标准化封装名
    comp.package = _normalize_api_package(comp.package_raw)

    # 检测参考前缀
    comp.ref_prefix = _detect_ref_prefix_api(comp)

    # 检测引脚数量
    comp.pin_count = _detect_pin_count_api(comp)

    # PADS 名称
    import re
    if comp.mfr_pn:
        safe_name = re.sub(r'[^A-Za-z0-9_.-]', '_', comp.mfr_pn)
        comp.pads_part_name = safe_name[:40]
    else:
        safe_name = re.sub(r'[^A-Za-z0-9_.-]', '_',
                           comp.digikey_pn or "UNKNOWN")
        comp.pads_part_name = safe_name[:40]

    comp.pads_decal_name = comp.package if comp.package else "UNKNOWN"

    return comp


def _normalize_api_package(raw_package):
    """标准化 API 返回的封装名"""
    if not raw_package:
        return ""

    import re

    raw = raw_package.strip()

    # 查映射表
    if raw in PACKAGE_NORMALIZE:
        return PACKAGE_NORMALIZE[raw]

    raw_lower = raw.lower()
    for key, value in PACKAGE_NORMALIZE.items():
        if key.lower() == raw_lower:
            return value

    # 尝试提取 4 位数的封装代号（如 0402, 0603）
    m = re.match(r'^(\d{4})(?:\s|$|\()', raw)
    if m:
        return m.group(1)

    # 尝试 XX-TYPE 模式
    m = re.match(r'(\d+)[-\s]*(SOIC|TSSOP|SSOP|MSOP|QFN|DFN|LQFP|TQFP|QFP|DIP|SOP)',
                 raw, re.IGNORECASE)
    if m:
        return f"{m.group(2).upper()}{m.group(1)}"

    cleaned = re.sub(r'[^A-Za-z0-9_-]', '_', raw)
    return cleaned[:20] if cleaned else "UNKNOWN"


def _detect_ref_prefix_api(comp):
    """根据 API 返回信息检测参考符号前缀"""
    text = f"{comp.description} {comp.category}".lower()
    for prefix, keywords in CATEGORY_PREFIXES.items():
        for kw in keywords:
            if kw.lower() in text:
                return prefix
    return "U"


def _detect_pin_count_api(comp):
    """从 API 信息检测引脚数"""
    import re
    pkg = comp.package

    two_pin = ["0201", "0402", "0603", "0805", "1206", "1210",
               "1812", "2010", "2512", "SMA", "SMB", "SMC"]
    if pkg in two_pin:
        return 2

    if pkg == "SOT23":
        return 3
    if pkg in ("SOT23-5", "SC70-5"):
        return 5
    if pkg in ("SOT23-6", "SC70-6", "SOT363"):
        return 6
    if pkg == "SOT223":
        return 4
    if pkg in ("TO92", "TO220", "DPAK"):
        return 3

    m = re.search(r'(\d+)$', pkg)
    if m:
        return int(m.group(1))

    return 2


def convert_api_results(products):
    """
    批量转换 DigiKey API 产品列表为 Component 列表

    Args:
        products: DigiKey API 返回的产品列表

    Returns:
        list[Component]
    """
    components = []
    seen = set()

    for product in products:
        comp = api_product_to_component(product)
        # 按 MPN 去重
        key = comp.mfr_pn or comp.digikey_pn
        if key and key not in seen:
            seen.add(key)
            components.append(comp)

    return components


# ============================================================
# 配置文件管理（保存/读取 API 凭据）
# ============================================================

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".digikey_pads_config.json")


def save_api_config(client_id, client_secret, use_sandbox=False):
    """保存 API 配置 (注意: 生产环境中应使用更安全的存储方式)"""
    config = {
        "client_id": client_id,
        "client_secret": client_secret,
        "use_sandbox": use_sandbox,
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def load_api_config():
    """加载已保存的 API 配置"""
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None
