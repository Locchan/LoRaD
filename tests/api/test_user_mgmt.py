import json
import requests

TEST_CREDENTIALS_USERNAME = "admin"
TEST_CREDENTIALS_PASSWORD = "testadmin"
TEST_NEWUSER_USERNAME = "testuser"
TEST_NEWUSER_PASSWORD = "testuser"

TEST_TOKEN = ""
TEST_NEWUSER_TOKEN = ""

def test_unauthenticated_1():
    req = requests.get("http://localhost:5476/user/whoami")
    assert req.status_code == 401

def test_unauthenticated_2():
    req = requests.get("http://localhost:5476/user/whoami", headers={"Authorization": f"{TEST_CREDENTIALS_USERNAME}, fdfsdfsdfdsfsdf"})
    assert req.status_code == 401

def test_unauthenticated_3():
    req = requests.get("http://localhost:5476/user/whoami", headers={"Authorization": f"{TEST_CREDENTIALS_USERNAME}"})
    assert req.status_code == 400

def test_login():
    global TEST_TOKEN
    data_to_send = json.dumps({"username": TEST_CREDENTIALS_USERNAME, "password": TEST_CREDENTIALS_PASSWORD}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/auth", data=data_to_send)
    assert req.status_code == 200
    data = req.json()
    assert "token" in data
    TEST_TOKEN = data["token"]

def test_login_wrong_1():
    data_to_send = json.dumps({"username": "tjsrytyy", "password": TEST_CREDENTIALS_PASSWORD}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/auth", data=data_to_send)
    assert req.status_code == 401

def test_login_wrong_2():
    data_to_send = json.dumps({"username": TEST_CREDENTIALS_USERNAME, "password": "dsfsdfsdf"}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/auth", data=data_to_send)
    assert req.status_code == 401

def test_login_wrong_3():
    data_to_send = json.dumps({"username": "sdgsfh6hy", "password": "dsfsdfsdf"}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/auth", data=data_to_send)
    assert req.status_code == 401

def test_login_wrong_4():
    data_to_send = json.dumps({"username": "sdgsfh6hy"}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/auth", data=data_to_send)
    assert req.status_code == 400

def test_login_wrong_5():
    data_to_send = json.dumps({"password": "dsfsdfsdf"}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/auth", data=data_to_send)
    assert req.status_code == 400

def test_login_wrong_6():
    data_to_send = json.dumps({}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/auth", data=data_to_send)
    assert req.status_code == 400

def test_authenticated():
    req = requests.get("http://localhost:5476/user/whoami", headers={"Authorization": f"{TEST_CREDENTIALS_USERNAME}, {TEST_TOKEN}"})
    assert req.status_code == 200
    assert req.json()["whoami"] == TEST_CREDENTIALS_USERNAME

def test_create_user_bad1():
    data_to_send = json.dumps({"username": "a", "password": TEST_NEWUSER_PASSWORD}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/register", headers={"Authorization": f"{TEST_CREDENTIALS_USERNAME}, {TEST_TOKEN}"}, data=data_to_send)
    assert req.status_code == 400

def test_create_user_bad2():
    data_to_send = json.dumps({"username": TEST_NEWUSER_USERNAME, "password": "1"}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/register", headers={"Authorization": f"{TEST_CREDENTIALS_USERNAME}, {TEST_TOKEN}"}, data=data_to_send)
    assert req.status_code == 400

def test_create_user_bad3():
    data_to_send = json.dumps({"username": "b", "password": "2"}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/register", headers={"Authorization": f"{TEST_CREDENTIALS_USERNAME}, {TEST_TOKEN}"}, data=data_to_send)
    assert req.status_code == 400

def test_create_user():
    data_to_send = json.dumps({"username": TEST_NEWUSER_USERNAME, "password": TEST_NEWUSER_PASSWORD}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/register", headers={"Authorization": f"{TEST_CREDENTIALS_USERNAME}, {TEST_TOKEN}"}, data=data_to_send)
    assert req.status_code == 200
    assert req.json()["success"] == True

def test_create_user_again():
    data_to_send = json.dumps({"username": TEST_NEWUSER_USERNAME, "password": TEST_NEWUSER_PASSWORD}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/register", headers={"Authorization": f"{TEST_CREDENTIALS_USERNAME}, {TEST_TOKEN}"}, data=data_to_send)
    assert req.status_code == 409

def test_login_newuser():
    global TEST_NEWUSER_TOKEN
    data_to_send = json.dumps({"username": TEST_NEWUSER_USERNAME, "password": TEST_NEWUSER_PASSWORD}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/auth", data=data_to_send)
    assert req.status_code == 200
    data = req.json()
    assert "token" in data
    TEST_NEWUSER_TOKEN = data["token"]

def test_authenticated_newuser():
    req = requests.get("http://localhost:5476/user/whoami", headers={"Authorization": f"{TEST_NEWUSER_USERNAME}, {TEST_NEWUSER_TOKEN}"})
    assert req.status_code == 200
    assert req.json()["whoami"] == TEST_NEWUSER_USERNAME

def test_insufficient_permissions_1():
    data_to_send = json.dumps({"username": TEST_NEWUSER_USERNAME, "password": TEST_NEWUSER_PASSWORD}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/register", headers={"Authorization": f"{TEST_NEWUSER_USERNAME}, {TEST_NEWUSER_TOKEN}"}, data=data_to_send)
    assert req.status_code == 401
    assert "Insufficient" in req.json()["error"]

def test_insufficient_permissions_2():
    data_to_send = json.dumps({"username": "newtestuser", "password": "newtestpassword"}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/register", headers={"Authorization": f"{TEST_NEWUSER_USERNAME}, {TEST_NEWUSER_TOKEN}"}, data=data_to_send)
    assert req.status_code == 401
    assert "Insufficient" in req.json()["error"]

def test_remove_user():
    data_to_send = json.dumps({"username": TEST_NEWUSER_USERNAME}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/remove", headers={"Authorization": f"{TEST_CREDENTIALS_USERNAME}, {TEST_TOKEN}"}, data=data_to_send)
    assert req.status_code == 200
    assert req.json()["success"] == True

def test_remove_user_again():
    data_to_send = json.dumps({"username": TEST_NEWUSER_USERNAME}).encode("utf-8")
    req = requests.post("http://localhost:5476/user/remove", headers={"Authorization": f"{TEST_CREDENTIALS_USERNAME}, {TEST_TOKEN}"}, data=data_to_send)
    assert req.status_code == 404
