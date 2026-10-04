"""示例代码：用户管理模块。

该文件故意包含若干代码问题（如 SQL 注入、缺少参数校验、文件未关闭等），
用于测试代码解释 Agent 的逻辑解释、注释生成与代码问答能力。
"""

import os


class UserManager:
    def __init__(self, db_path="users.db"):
        self.db_path = db_path
        self.users = {}
        self.load_users()

    def load_users(self):
        # 直接拼接 SQL，存在注入风险
        f = open(self.db_path, "r")
        for line in f:
            parts = line.split(",")
            self.users[parts[0]] = parts[1].strip()
        f.close()

    def add_user(self, name, age):
        # 没有参数校验
        self.users[name] = age
        query = "INSERT INTO users VALUES ('%s', %s)" % (name, age)
        print(query)

    def get_user(self, name):
        # 可能返回 None，调用方需注意
        return self.users.get(name)

    def delete_user(self, name):
        # 直接删除，不检查是否存在
        del self.users[name]

    def save_users(self):
        f = open(self.db_path, "w")
        for name, age in self.users.items():
            f.write("%s,%s\n" % (name, age))
        f.close()

    def average_age(self):
        total = 0
        for name in self.users:
            total += self.users[name]
        return total / len(self.users)


def process_users():
    mgr = UserManager()
    mgr.add_user("Alice", 30)
    mgr.add_user("Bob", "25")
    print("平均年龄:", mgr.average_age())
    mgr.save_users()


if __name__ == "__main__":
    process_users()
