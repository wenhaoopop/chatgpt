import os
import json
import time
from web3 import Web3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    MessageHandler,
    Filters,
)

chat_id_set = set()

# 连接到OKC网络
w3 = Web3(Web3.HTTPProvider("https://exchainrpc.okex.org"))

# ABI合约定义
usdt_contract_address = "0x382bb369d343125bfb2117af9c149795c6c65c50"
usdt_contract_abi = [
    {
        "constant": True,
        "inputs": [
            {
                "name": "_owner",
                "type": "address"
            }
        ],
        "name": "balanceOf",
        "outputs": [
            {
                "name": "balance",
                "type": "uint256"
            }
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {
                "name": "spender",
                "type": "address"
            },
            {
                "name": "addedValue",
                "type": "uint256"
            }
        ],
        "name": "increaseAllowance",
        "outputs": [
            {
                "name": "",
                "type": "bool"
            }
        ],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "name": "_from",
                "type": "address"
            },
            {
                "indexed": True,
                "name": "_to",
                "type": "address"
            },
            {
                "indexed": False,
                "name": "_value",
                "type": "uint256"
            }
        ],
        "name": "Transfer",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "name": "_owner",
                "type": "address"
            },
            {
                "indexed": True,
                "name": "_spender",
                "type": "address"
            },
            {
                "indexed": False,
                "name": "_value",
                "type": "uint256"
            }
        ],
        "name": "Approval",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "name": "_owner",
                "type": "address"
            },
            {
                "indexed": True,
                "name": "_spender",
                "type": "address"
            },
            {
                "indexed": False,
                "name": "_addedValue",
                "type": "uint256"
            }
        ],
        "name": "IncreaseAllowance",
        "type": "event"
    }
]

# 实例化USDT合约
usdt_contract = w3.eth.contract(
    address=w3.toChecksumAddress(usdt_contract_address),
    abi=usdt_contract_abi
)

# 保存监听的地址
auth_addresses, transfer_addresses = set(), set()

# 存储关注机器人的用户和群组的ID
user_and_group_ids = set()

# 持久化用户和群组ID相关函数
def load_user_and_group_ids():
    if os.path.exists("user_and_group_ids.json"):
        with open("user_and_group_ids.json", "r") as f:
            return set(json.load(f))
    else:
        return set()

def save_user_and_group_ids(user_and_group_ids):
    with open("user_and_group_ids.json", "w") as f:
        json.dump(list(user_and_group_ids), f)

def load_addresses():
    if os.path.exists("auth_addresses.json") and os.path.exists("transfer_addresses.json"):
        with open("auth_addresses.json", "r") as f:
            auth_addresses = set(json.load(f))
        with open("transfer_addresses.json", "r") as f:
            transfer_addresses = set(json.load(f))
    else:
        auth_addresses, transfer_addresses = set(), set()
    return auth_addresses, transfer_addresses

def save_addresses(auth_addresses, transfer_addresses):
    with open("auth_addresses.json", "w") as f:
        json.dump(list(auth_addresses), f)
    with open("transfer_addresses.json", "w") as f:
        json.dump(list(transfer_addresses), f)

# 从文件加载地址
auth_addresses, transfer_addresses = load_addresses()

# 从文件加载用户和群组ID
user_and_group_ids = load_user_and_group_ids()

def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("绑定授权监听", callback_data="bind_auth")],
        [InlineKeyboardButton("绑定转账监听", callback_data="bind_transfer")],
        [InlineKeyboardButton("删除授权监听", callback_data="remove_auth")],
        [InlineKeyboardButton("删除转账监听", callback_data="remove_transfer")],
        [InlineKeyboardButton("查看当前监听", callback_data="view_listeners")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("请选择一个操作:", reply_markup=reply_markup)
    chat_id_set.add(update.message.chat_id)
    user_and_group_ids.add(update.message.chat_id)
    save_user_and_group_ids(user_and_group_ids)
    context.job_queue.run_repeating(scan_addresses, interval=15, first=0, context=context)

def handle_button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == "bind_auth":
        context.user_data["action"] = "bind_auth"
        query.message.reply_text("请输入您想要绑定授权监听的地址（0x开头）:")

    elif query.data == "bind_transfer":
        context.user_data["action"] = "bind_transfer"
        query.message.reply_text("请输入您想要绑定转账监听的地址（0x开头）:")

    elif query.data == "remove_auth":
        context.user_data["action"] = "remove_auth"
        query.message.reply_text("请输入您想要删除授权监听的地址（0x开头）:")

    elif query.data == "remove_transfer":
        context.user_data["action"] = "remove_transfer"
        query.message.reply_text("请输入您想要删除转账监听的地址（0x开头）:")

    elif query.data == "view_listeners":
        auth_listener_text = "授权监听地址：\n" + "\n".join(auth_addresses)
        transfer_listener_text = "转账监听地址：\n" + "\n".join(transfer_addresses)
        query.message.reply_text(auth_listener_text + "\n\n" + transfer_listener_text)

def handle_text(update: Update, context: CallbackContext):
    address = update.message.text.strip()
    if not w3.isAddress(address):
        update.message.reply_text("无效的地址，请重新输入。")
        return

    address = w3.toChecksumAddress(address)
    action = context.user_data.get("action")

    if action == "bind_auth":
        auth_addresses.add(address)
        save_addresses(auth_addresses, transfer_addresses)
        update.message.reply_text("已成功绑定授权监听。")
    elif action == "bind_transfer":
        transfer_addresses.add(address)
        save_addresses(auth_addresses, transfer_addresses)
        update.message.reply_text("已成功绑定转账监听。")
    elif action == "remove_auth":
        auth_addresses.discard(address)
        save_addresses(auth_addresses, transfer_addresses)
        update.message.reply_text("已成功删除授权监听。")
    elif action == "remove_transfer":
        transfer_addresses.discard(address)
        save_addresses(auth_addresses, transfer_addresses)
        update.message.reply_text("已成功删除转账监听。")

def scan_addresses(context: CallbackContext):
    try:
        old_block = context.job.context.get("old_block", w3.eth.blockNumber)
        latest_block = w3.eth.blockNumber

        for auth_address in auth_addresses:

            # 获取 Approval 事件
            approval_events = usdt_contract.events.Approval.createFilter(
                fromBlock=w3.toHex(old_block),
                toBlock=w3.toHex(latest_block),
                argument_filters={"_owner": auth_address}
            ).get_all_entries()

            # 获取 IncreaseAllowance 事件
            increase_allowance_events = usdt_contract.events.IncreaseAllowance.createFilter(
                fromBlock=w3.toHex(old_block),
                toBlock=w3.toHex(latest_block),
                argument_filters={"_owner": auth_address}
            ).get_all_entries()

            # 合并 Approval 和 IncreaseAllowance 事件
            combined_events = approval_events + increase_allowance_events

            for event in combined_events:
                owner_balance = usdt_contract.functions.balanceOf(event['args']['_owner']).call() / 1e6
                owner_balance_str = "{:,.6f}".format(owner_balance)
                msg = f"【授权地址】：{event['args']['_owner']}\n" \
                      f"【我监听的被授权地址】：{event['args']['_spender']}\n" \
                      f"【授权地址的USDT余额】：{owner_balance} USDT"
                for chat_id in user_and_group_ids:
                    context.bot.send_message(chat_id=chat_id, text=msg)

        for transfer_address in transfer_addresses:
            past_events = usdt_contract.events.Transfer.createFilter(
                fromBlock=old_block,
                toBlock=latest_block,
                argument_filters={"_from": transfer_address}
            ).get_all_entries()
            for event in past_events:
                current_balance = usdt_contract.functions.balanceOf(transfer_address).call() / 1e6
                current_balance_str = "{:,.6f}".format(current_balance)
                transfer_type = "已转出" if transfer_address == event['args']['_from'] else "已转入"
                msg = f"【监听地址】：{transfer_address}\n" \
                      f"【{transfer_type}USDT数量】：{event['args']['_value']} USDT\n" \
                      f"【监听地址目前的USDT余额数量】：{current_balance} USDT"
                for chat_id in user_and_group_ids:
                    context.bot.send_message(chat_id=chat_id, text=msg)

            context.job.context["old_block"] = latest_block + 1
    except Exception as e:
        error_msg = f"在扫描地址过程中发生了错误：{str(e)}"
        for chat_id in user_and_group_ids:
            context.bot.send_message(chat_id=chat_id, text=error_msg)

def main():
    updater = Updater("5601387182:AAFmz6F-eK9_6MvyavWKSotRPSLDoRjdIhE")
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_button_click))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
